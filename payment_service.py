#!/usr/bin/env python3
"""
Payment bridge: HTTP REST ↔ INPAS DualConnector TCP/XML.
Translates requests from Chrome into TCP commands for PAX S300 via DC Service.

Architecture:
  Chrome (fetch) → HTTP localhost:5050 → this service → TCP localhost:DC_PORT → DC Service → USB → PAX S300 → Ethernet → Bank

Usage:
  python payment_service.py
  python payment_service.py --dc-port 8888

Environment variables:
  DC_HOST  — DualConnector host (default: 127.0.0.1)
  DC_PORT  — DualConnector TCP port (default: 8888)
  PAY_PORT — This service HTTP port (default: 5050)
"""

import http.server
import json
import socket
import struct
import threading
import xml.etree.ElementTree as ET
import os
import sys
import time
import traceback
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DC_HOST = os.environ.get('DC_HOST', '127.0.0.1')
DC_PORT = int(os.environ.get('DC_PORT', '9015'))
PAY_PORT = int(os.environ.get('PAY_PORT', '5050'))
DC_TIMEOUT = 120   # seconds — enough for card tap + bank authorization
SETTLEMENT_TIME = os.environ.get('SETTLEMENT_TIME', '23:55')  # HH:MM — auto-settlement

# INPAS SmartSale operation codes
OP_PURCHASE   = 1
OP_CANCEL     = 2
OP_REFUND     = 3
OP_SETTLEMENT = 7
OP_STATUS     = 50

CURRENCY_RUB = 643


# ---------------------------------------------------------------------------
# DualConnector TCP protocol (4-byte big-endian length + XML body)
# ---------------------------------------------------------------------------

def build_xml(operation_code, amount=None, currency=CURRENCY_RUB, rrn=None):
    """Build XML request for DualConnector 2.x."""
    root = ET.Element('request')
    ET.SubElement(root, 'operation_code').text = str(operation_code)
    if amount is not None:
        ET.SubElement(root, 'amount').text = str(int(amount))
    ET.SubElement(root, 'currency_code').text = str(currency)
    if rrn:
        ET.SubElement(root, 'rrn').text = str(rrn)

    xml_decl = '<?xml version="1.0" encoding="windows-1251"?>\n'
    body = ET.tostring(root, encoding='unicode')
    return xml_decl + body


def send_to_dc(xml_str, timeout=DC_TIMEOUT):
    """Send XML to DualConnector via TCP and return response XML string."""
    encoded = xml_str.encode('windows-1251')
    header = struct.pack('>I', len(encoded))

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((DC_HOST, DC_PORT))
        sock.sendall(header + encoded)

        # Read 4-byte response length
        resp_hdr = _recv_exact(sock, 4)
        resp_len = struct.unpack('>I', resp_hdr)[0]

        # Read response body
        resp_body = _recv_exact(sock, resp_len)
        return resp_body.decode('windows-1251')
    finally:
        sock.close()


def _recv_exact(sock, n):
    """Read exactly n bytes from socket."""
    buf = b''
    while len(buf) < n:
        chunk = sock.recv(min(4096, n - len(buf)))
        if not chunk:
            raise ConnectionError('DualConnector closed connection')
        buf += chunk
    return buf


def parse_response(xml_str):
    """Parse DC response XML into a flat dict (lowercase keys)."""
    try:
        root = ET.fromstring(xml_str)
        return {child.tag.lower(): (child.text or '') for child in root}
    except ET.ParseError as e:
        return {'parse_error': str(e), 'raw_xml': xml_str}


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
            xml_resp = send_to_dc(xml_req, timeout=DC_TIMEOUT)
            result = parse_response(xml_resp)

            code = result.get('response_code', '')
            success = (code == '00')

            response = {
                'success':            success,
                'response_code':      code,
                'message':            result.get('response_text', result.get('message', '')),
                'rrn':                result.get('rrn', ''),
                'authorization_code': result.get('authorization_code', ''),
                'card_number':        result.get('card_number', ''),
                'terminal_id':        result.get('terminal_id', ''),
            }
            tag = 'OK' if success else f'DECLINED ({code})'
            print(f'[PAY] Result: {tag}, rrn={response["rrn"]}')
            self._send_json(200, response)

        except socket.timeout:
            print('[PAY] Timeout')
            self._send_json(504, {
                'success': False,
                'error': 'Таймаут ожидания терминала. Попробуйте ещё раз.',
            })
        except ConnectionRefusedError:
            print('[PAY] DualConnector not running')
            self._send_json(503, {
                'success': False,
                'error': 'Терминал оплаты не подключён (DualConnector не запущен).',
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
            success = result.get('response_code') == '00'
            self._send_json(200, {
                'success': success,
                'response_code': result.get('response_code', ''),
                'message': result.get('response_text', result.get('message', '')),
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
            success = result.get('response_code') == '00'
            self._send_json(200, {
                'success': success,
                'response_code': result.get('response_code', ''),
                'message': result.get('response_text', result.get('message', '')),
            })
        except Exception as e:
            print(f'[REFUND] Error: {e}')
            self._send_json(500, {'success': False, 'error': str(e)})

    def _handle_status(self):
        """POST|GET /api/status — check terminal connectivity."""
        try:
            xml_req = build_xml(OP_STATUS)
            xml_resp = send_to_dc(xml_req, timeout=10)
            result = parse_response(xml_resp)
            success = result.get('response_code') == '00'
            self._send_json(200, {
                'success': success,
                'connected': success,
                'message': result.get('response_text', result.get('message', '')),
            })
        except ConnectionRefusedError:
            self._send_json(200, {
                'success': False, 'connected': False,
                'error': 'DualConnector не запущен',
            })
        except socket.timeout:
            self._send_json(200, {
                'success': False, 'connected': False,
                'error': 'Таймаут подключения к терминалу',
            })
        except Exception as e:
            self._send_json(200, {
                'success': False, 'connected': False,
                'error': str(e),
            })

    def _handle_settlement(self):
        """POST /api/settlement — end-of-day settlement (сверка итогов)."""
        try:
            print('[SETTLEMENT] Starting...')
            xml_req = build_xml(OP_SETTLEMENT)
            xml_resp = send_to_dc(xml_req, timeout=60)
            result = parse_response(xml_resp)
            success = result.get('response_code') == '00'
            tag = 'OK' if success else 'FAILED'
            print(f'[SETTLEMENT] {tag}')
            self._send_json(200, {
                'success': success,
                'message': result.get('response_text', result.get('message', '')),
            })
        except Exception as e:
            print(f'[SETTLEMENT] Error: {e}')
            self._send_json(500, {'success': False, 'error': str(e)})

    def log_message(self, fmt, *args):
        print(f'[{time.strftime("%H:%M:%S")}] {args[0] if args else fmt}')


# ---------------------------------------------------------------------------
# Auto-settlement scheduler (background thread)
# ---------------------------------------------------------------------------

def run_settlement():
    """Execute settlement operation and return success flag."""
    try:
        print(f'[SETTLEMENT] Auto-settlement starting at {time.strftime("%H:%M:%S")}')
        xml_req = build_xml(OP_SETTLEMENT)
        xml_resp = send_to_dc(xml_req, timeout=60)
        result = parse_response(xml_resp)
        success = result.get('response_code') == '00'
        msg = result.get('response_text', result.get('message', ''))
        tag = 'OK' if success else 'FAILED'
        print(f'[SETTLEMENT] Auto-settlement {tag}: {msg}')
        return success
    except Exception as e:
        print(f'[SETTLEMENT] Auto-settlement error: {e}')
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
        print(f'[SETTLEMENT] Next auto-settlement at {target.strftime("%Y-%m-%d %H:%M")}'
              f' (in {int(wait_seconds // 3600)}h {int((wait_seconds % 3600) // 60)}m)')
        time.sleep(wait_seconds)
        run_settlement()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    # CLI overrides
    for i, arg in enumerate(sys.argv):
        if arg == '--dc-port' and i + 1 < len(sys.argv):
            DC_PORT = int(sys.argv[i + 1])
        if arg == '--settlement-time' and i + 1 < len(sys.argv):
            SETTLEMENT_TIME = sys.argv[i + 1]

    print('=' * 50)
    print('  PAX S300 Payment Service')
    print('=' * 50)
    print(f'  HTTP listen:       0.0.0.0:{PAY_PORT}')
    print(f'  DualConnector:     {DC_HOST}:{DC_PORT}')
    print(f'  DC timeout:        {DC_TIMEOUT}s')
    print(f'  Auto-settlement:   {SETTLEMENT_TIME}')
    print('=' * 50)

    # Start auto-settlement background thread
    settler = threading.Thread(target=settlement_scheduler, daemon=True)
    settler.start()

    server = http.server.HTTPServer(('0.0.0.0', PAY_PORT), PaymentHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[PAYMENT] Shutting down')
        server.server_close()
