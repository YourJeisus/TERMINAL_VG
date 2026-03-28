#!/usr/bin/env python3
"""
Payment bridge: HTTP REST <-> INPAS DualConnector HTTP/XML.
Translates requests from Chrome into HTTP POST commands for DC Service.

Architecture:
  Chrome (fetch) -> HTTP localhost:5050 -> this service -> HTTP localhost:9015 -> DC Service -> COM3 -> PAX S300 -> Bank

Usage:
  python payment_service.py
  python payment_service.py --dc-port 9015
"""

import http.server
import json
import threading
import xml.etree.ElementTree as ET
import os
import sys
import time
import traceback
import urllib.request
import urllib.error
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DC_HOST = os.environ.get('DC_HOST', '127.0.0.1')
DC_PORT = int(os.environ.get('DC_PORT', '9015'))
PAY_PORT = int(os.environ.get('PAY_PORT', '5050'))
DC_TIMEOUT = 120   # seconds
SETTLEMENT_TIME = os.environ.get('SETTLEMENT_TIME', '23:55')

# INPAS field IDs (ISO 8583 based)
# Field 00: Operation type
# Field 04: Amount (kopecks)
# Field 20: Currency code
# Field 37: RRN (for cancel/refund)

OP_PURCHASE   = '1'
OP_CANCEL     = '2'
OP_REFUND     = '3'
OP_SETTLEMENT = '7'
OP_STATUS     = '50'

CURRENCY_RUB = '643'


# ---------------------------------------------------------------------------
# DualConnector HTTP protocol (POST XML to http://host:port/)
# ---------------------------------------------------------------------------

def build_xml(operation_code, amount=None, currency=CURRENCY_RUB, rrn=None):
    """Build INPAS field-based XML request."""
    root = ET.Element('request')
    ET.SubElement(root, 'field', id='00').text = str(operation_code)
    if amount is not None:
        ET.SubElement(root, 'field', id='04').text = str(int(amount))
    ET.SubElement(root, 'field', id='20').text = str(currency)
    if rrn:
        ET.SubElement(root, 'field', id='37').text = str(rrn)

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode')


def send_to_dc(xml_str, timeout=DC_TIMEOUT):
    """Send XML to DualConnector via HTTP POST and return response XML string."""
    url = f'http://{DC_HOST}:{DC_PORT}/'
    data = xml_str.encode('utf-8')

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            'Content-Type': 'application/xml; charset=utf-8',
            'Content-Length': str(len(data)),
        },
        method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_body = resp.read()
            # Try UTF-8 first, then windows-1251
            try:
                return resp_body.decode('utf-8')
            except UnicodeDecodeError:
                return resp_body.decode('windows-1251')
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        raise Exception(f'DC HTTP {e.code}: {body[:300]}')


def parse_response(xml_str):
    """Parse INPAS field-based XML response into a dict keyed by field id."""
    try:
        root = ET.fromstring(xml_str)
        result = {}
        for child in root:
            if child.tag == 'field':
                fid = child.get('id', '')
                result[fid] = child.text or ''
            else:
                # Fallback: tag-based format
                result[child.tag.lower()] = child.text or ''
        return result
    except ET.ParseError as e:
        return {'parse_error': str(e), 'raw_xml': xml_str}


def extract_response(result):
    """Extract standard fields from parsed INPAS response."""
    return {
        'response_code':      result.get('39', ''),
        'message':            result.get('48', result.get('message', '')),
        'rrn':                result.get('37', ''),
        'authorization_code': result.get('38', ''),
        'card_number':        result.get('34', result.get('19', '')),
        'terminal_id':        result.get('41', ''),
        'amount':             result.get('04', ''),
    }


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class PaymentHandler(http.server.BaseHTTPRequestHandler):

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path == '/api/status':
            self._handle_status()
        else:
            self.send_error(404)

    def do_POST(self):
        routes = {
            '/api/pay':        self._handle_pay,
            '/api/cancel':     self._handle_cancel,
            '/api/refund':     self._handle_refund,
            '/api/status':     self._handle_status,
            '/api/settlement': self._handle_settlement,
        }
        handler = routes.get(self.path)
        if handler:
            handler()
        else:
            self.send_error(404)

    # --- helpers ---

    def _read_json(self):
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def _send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(body)

    # --- endpoints ---

    def _handle_pay(self):
        """POST /api/pay  {amount: kopecks, order_id: string}"""
        try:
            params = self._read_json()
            amount = params.get('amount')
            order_id = params.get('order_id', '')

            if not amount or int(amount) <= 0:
                self._send_json(400, {'success': False, 'error': 'Invalid amount'})
                return

            print(f'[PAY] Purchase: {int(amount)} kopecks, order={order_id}')

            xml_req = build_xml(OP_PURCHASE, amount=int(amount))
            print(f'[PAY] Sending XML: {xml_req}')

            xml_resp = send_to_dc(xml_req, timeout=DC_TIMEOUT)
            print(f'[PAY] Response XML: {xml_resp[:500]}')

            result = parse_response(xml_resp)
            fields = extract_response(result)

            code = fields['response_code']
            success = (code == '00')

            response = {
                'success':            success,
                'response_code':      code,
                'message':            fields['message'],
                'rrn':                fields['rrn'],
                'authorization_code': fields['authorization_code'],
                'card_number':        fields['card_number'],
                'terminal_id':        fields['terminal_id'],
                'raw_fields':         result,  # For debugging
            }
            tag = 'OK' if success else f'DECLINED ({code})'
            print(f'[PAY] Result: {tag}, rrn={fields["rrn"]}')
            self._send_json(200, response)

        except urllib.error.URLError as e:
            print(f'[PAY] Connection error: {e}')
            self._send_json(503, {
                'success': False,
                'error': f'DualConnector not available: {e.reason}',
            })
        except Exception as e:
            print(f'[PAY] Error: {e}')
            traceback.print_exc()
            self._send_json(500, {'success': False, 'error': str(e)})

    def _handle_cancel(self):
        """POST /api/cancel  {amount: kopecks, rrn: string}"""
        try:
            params = self._read_json()
            amount = params.get('amount')
            rrn = params.get('rrn')
            if not amount or not rrn:
                self._send_json(400, {'success': False, 'error': 'amount and rrn required'})
                return

            print(f'[CANCEL] amount={amount}, rrn={rrn}')
            xml_req = build_xml(OP_CANCEL, amount=int(amount), rrn=rrn)
            xml_resp = send_to_dc(xml_req)
            result = parse_response(xml_resp)
            fields = extract_response(result)
            success = fields['response_code'] == '00'
            self._send_json(200, {
                'success': success,
                'response_code': fields['response_code'],
                'message': fields['message'],
            })
        except Exception as e:
            print(f'[CANCEL] Error: {e}')
            self._send_json(500, {'success': False, 'error': str(e)})

    def _handle_refund(self):
        """POST /api/refund  {amount: kopecks, rrn: string}"""
        try:
            params = self._read_json()
            amount = params.get('amount')
            rrn = params.get('rrn')
            if not amount or not rrn:
                self._send_json(400, {'success': False, 'error': 'amount and rrn required'})
                return

            print(f'[REFUND] amount={amount}, rrn={rrn}')
            xml_req = build_xml(OP_REFUND, amount=int(amount), rrn=rrn)
            xml_resp = send_to_dc(xml_req)
            result = parse_response(xml_resp)
            fields = extract_response(result)
            success = fields['response_code'] == '00'
            self._send_json(200, {
                'success': success,
                'response_code': fields['response_code'],
                'message': fields['message'],
            })
        except Exception as e:
            print(f'[REFUND] Error: {e}')
            self._send_json(500, {'success': False, 'error': str(e)})

    def _handle_status(self):
        """POST|GET /api/status"""
        try:
            xml_req = build_xml(OP_STATUS)
            xml_resp = send_to_dc(xml_req, timeout=10)
            result = parse_response(xml_resp)
            fields = extract_response(result)
            success = fields['response_code'] == '00'
            self._send_json(200, {
                'success': success,
                'connected': success,
                'message': fields['message'],
                'raw_fields': result,
            })
        except urllib.error.URLError:
            self._send_json(200, {
                'success': False, 'connected': False,
                'error': 'DualConnector HTTP not available',
            })
        except Exception as e:
            self._send_json(200, {
                'success': False, 'connected': False,
                'error': str(e),
            })

    def _handle_settlement(self):
        """POST /api/settlement"""
        try:
            print('[SETTLEMENT] Starting...')
            xml_req = build_xml(OP_SETTLEMENT)
            xml_resp = send_to_dc(xml_req, timeout=60)
            result = parse_response(xml_resp)
            fields = extract_response(result)
            success = fields['response_code'] == '00'
            tag = 'OK' if success else 'FAILED'
            print(f'[SETTLEMENT] {tag}')
            self._send_json(200, {
                'success': success,
                'message': fields['message'],
            })
        except Exception as e:
            print(f'[SETTLEMENT] Error: {e}')
            self._send_json(500, {'success': False, 'error': str(e)})

    def log_message(self, fmt, *args):
        print(f'[{time.strftime("%H:%M:%S")}] {args[0] if args else fmt}')


# ---------------------------------------------------------------------------
# Auto-settlement scheduler
# ---------------------------------------------------------------------------

def run_settlement():
    """Execute settlement operation."""
    try:
        print(f'[SETTLEMENT] Auto-settlement at {time.strftime("%H:%M:%S")}')
        xml_req = build_xml(OP_SETTLEMENT)
        xml_resp = send_to_dc(xml_req, timeout=60)
        result = parse_response(xml_resp)
        fields = extract_response(result)
        success = fields['response_code'] == '00'
        print(f'[SETTLEMENT] {"OK" if success else "FAILED"}: {fields["message"]}')
        return success
    except Exception as e:
        print(f'[SETTLEMENT] Error: {e}')
        return False


def settlement_scheduler():
    """Background thread: runs settlement daily at SETTLEMENT_TIME."""
    while True:
        now = datetime.now()
        hour, minute = map(int, SETTLEMENT_TIME.split(':'))
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        print(f'[SETTLEMENT] Next at {target.strftime("%Y-%m-%d %H:%M")}'
              f' (in {int(wait_seconds // 3600)}h {int((wait_seconds % 3600) // 60)}m)')
        time.sleep(wait_seconds)
        run_settlement()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    for i, arg in enumerate(sys.argv):
        if arg == '--dc-port' and i + 1 < len(sys.argv):
            DC_PORT = int(sys.argv[i + 1])
        if arg == '--settlement-time' and i + 1 < len(sys.argv):
            SETTLEMENT_TIME = sys.argv[i + 1]

    print('=' * 50)
    print('  PAX S300 Payment Service')
    print('=' * 50)
    print(f'  HTTP listen:       0.0.0.0:{PAY_PORT}')
    print(f'  DualConnector:     http://{DC_HOST}:{DC_PORT}/')
    print(f'  Protocol:          HTTP POST (XML fields)')
    print(f'  DC timeout:        {DC_TIMEOUT}s')
    print(f'  Auto-settlement:   {SETTLEMENT_TIME}')
    print('=' * 50)

    settler = threading.Thread(target=settlement_scheduler, daemon=True)
    settler.start()

    server = http.server.HTTPServer(('0.0.0.0', PAY_PORT), PaymentHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[PAYMENT] Shutting down')
        server.server_close()
