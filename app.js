// === Initialize Lucide icons ===
lucide.createIcons();

// === API Configuration ===
var LOCAL_SERVER = 'http://localhost:9999';
var API_URL = LOCAL_SERVER + '/api/categories'; // proxied via server.py to bypass CORS
var TERMINAL_NAME = 'term1';
var TERMINAL_CODE = 'XRHxAIKHdBoDRujltXnc8H9C5ZBAwm4S';

// Map API category_id → screen key
var CATEGORY_SCREEN_MAP = {
  '1': 'tickets',    // Канатная дорога
  '2': 'alpaka',     // Парк Альпак
  '3': 'museum',     // Музей иллюзий
  '4': 'skypark'     // Skypark
};

var loadedCategories = [];

function loadCategories() {
  var xhr = new XMLHttpRequest();
  xhr.open('POST', API_URL, true);
  xhr.setRequestHeader('Content-Type', 'application/json');
  xhr.timeout = 10000;
  xhr.onload = function() {
    try {
      var data = JSON.parse(xhr.responseText);
      if (data.categories && data.categories.length > 0) {
        loadedCategories = data.categories;
        renderCategories(data.categories);
        console.log('[API] Loaded ' + data.categories.length + ' categories');
      }
    } catch (e) {
      console.error('[API] Parse error:', e);
    }
  };
  xhr.onerror = function() { console.error('[API] Network error'); };
  xhr.ontimeout = function() { console.error('[API] Timeout'); };
  xhr.send(JSON.stringify({
    terminal_name: TERMINAL_NAME,
    terminal_code: TERMINAL_CODE
  }));
}

function renderCategories(categories) {
  categories.forEach(function(cat) {
    var screenKey = CATEGORY_SCREEN_MAP[cat.category_id];
    if (!screenKey) return;
    var screenId = 'screen-' + screenKey;
    var screen = document.getElementById(screenId);
    if (!screen) return;

    // Update title
    var titleEl = screen.querySelector('.tkt-title');
    if (titleEl && cat.category_name) titleEl.textContent = cat.category_name;

    // Update description
    var descEl = screen.querySelector('.tkt-description p');
    if (descEl && cat.category_description) descEl.textContent = cat.category_description;

    // Update carousel photo if provided
    if (cat.category_photo) {
      var track = screen.querySelector('.tkt-carousel-track');
      if (track) {
        var img = document.createElement('img');
        img.src = cat.category_photo;
        img.alt = cat.category_name;
        img.className = 'tkt-carousel-slide';
        track.appendChild(img);
      }
    }

    // Render tariffs
    if (cat.category_tariffs && cat.category_tariffs.length > 0) {
      var rowsContainer = screen.querySelector('.tkt-rows');
      if (!rowsContainer) return;
      rowsContainer.innerHTML = '';

      cat.category_tariffs.forEach(function(tariff) {
        var row = document.createElement('div');
        row.className = 'tkt-row';
        row.dataset.price = tariff.price;
        row.dataset.tariffId = tariff.id;
        row.innerHTML =
          '<span class="tkt-pill">' + tariff.name + '</span>' +
          '<span class="tkt-price">' + formatPrice(parseInt(tariff.price)) + ' ₽</span>' +
          '<div class="tkt-counter">' +
            '<button class="tkt-counter-btn tkt-counter-btn--minus" onclick="changeQty(this, -1)">−</button>' +
            '<span class="tkt-counter-val">0</span>' +
            '<button class="tkt-counter-btn tkt-counter-btn--plus" onclick="changeQty(this, 1)">+</button>' +
          '</div>';
        rowsContainer.appendChild(row);
      });
    }
  });

  lucide.createIcons();
}

// Load categories on startup
loadCategories();

// === Navigation ===
const screenMap = {
  'splash': 'screen-splash',
  'main': 'screen-main',
  'scan-card': 'screen-scan-card',
  'topup': 'screen-topup',
  'tickets': 'screen-tickets',
  'alpaka': 'screen-alpaka',
  'museum': 'screen-museum',
  'skypark': 'screen-skypark',
  'rental': 'screen-rental',
  'instructors': 'screen-instructors',
  'payment': 'screen-payment',
  'sbp': 'screen-sbp',
  'success': 'screen-success'
};

function navigateTo(screenName) {
  const targetId = screenMap[screenName];
  if (!targetId) return;

  document.querySelectorAll('.screen.active').forEach(s => s.classList.remove('active'));
  const target = document.getElementById(targetId);
  if (target) {
    target.classList.add('active');
    target.querySelectorAll('.main-content, .topup-wrap, .tkt-scroll, .tkt-card, .rent-content, .instructors-content')
      .forEach(el => el.scrollTop = 0);
  }

  // Reset ticket/rental counters when navigating to those screens
  if (screenName === 'tickets') resetTickets();
  if (screenName === 'alpaka') resetScreen('screen-alpaka', 'alpaka-total');
  if (screenName === 'museum') resetScreen('screen-museum', 'museum-total');
  if (screenName === 'skypark') resetScreen('screen-skypark', 'skypark-total');
  if (screenName === 'rental') resetRental();
}

function resetTickets() {
  document.querySelectorAll('#screen-tickets .tkt-row').forEach(function(row) {
    row.classList.remove('tkt-row--selected');
    var val = row.querySelector('.tkt-counter-val');
    if (val) val.textContent = '0';
  });
  var comboVal = document.querySelector('.tkt-combo-counter-val');
  if (comboVal) comboVal.textContent = '0';
  var totalEl = document.getElementById('tickets-total');
  if (totalEl) totalEl.textContent = '0 ₽';
}

function resetRental() {
  document.querySelectorAll('#screen-rental .rent-qty-row').forEach(function(row) {
    row.classList.remove('rent-qty-row--selected');
    var val = row.querySelector('.rent-counter-val');
    if (val) val.textContent = '0';
  });
  var totalEl = document.getElementById('rental-total');
  if (totalEl) totalEl.textContent = '0 ₽';
}

function resetScreen(screenId, totalId) {
  document.querySelectorAll('#' + screenId + ' .tkt-row').forEach(function(row) {
    row.classList.remove('tkt-row--selected');
    var val = row.querySelector('.tkt-counter-val');
    if (val) val.textContent = '0';
  });
  var totalEl = document.getElementById(totalId);
  if (totalEl) totalEl.textContent = '0 ₽';
}

// === Toast/Alert ===
let toastTimer = null;
function showAlert(message) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('visible'), 2500);
}

// === Tab switching ===
document.addEventListener('click', (e) => {
  const tab = e.target.closest('.tab');
  if (!tab) return;
  const tabs = tab.parentElement;
  tabs.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  tab.classList.add('active');
});

// === Price selection (topup) ===
function selectPrice(el, price) {
  const card = el.closest('.topup-card');
  card.querySelectorAll('.topup-price-cell').forEach(p => p.classList.remove('selected'));
  el.classList.add('selected');
}

// === Ticket quantity ===
function changeQty(btn, delta) {
  const counter = btn.closest('.tkt-counter');
  const valueEl = counter.querySelector('.tkt-counter-val');
  const row = btn.closest('.tkt-row');
  let val = parseInt(valueEl.textContent) + delta;
  if (val < 0) val = 0;
  valueEl.textContent = val;

  if (val > 0) {
    row.classList.add('tkt-row--selected');
  } else {
    row.classList.remove('tkt-row--selected');
  }

  updateTicketsTotal();
}

function updateTicketsTotal() {
  // Find currently active ticket screen
  var screens = [
    { id: 'screen-tickets', totalId: 'tickets-total', hasCombo: true },
    { id: 'screen-alpaka', totalId: 'alpaka-total', hasCombo: false },
    { id: 'screen-museum', totalId: 'museum-total', hasCombo: false },
    { id: 'screen-skypark', totalId: 'skypark-total', hasCombo: false }
  ];

  for (var s = 0; s < screens.length; s++) {
    var screen = document.getElementById(screens[s].id);
    if (!screen || !screen.classList.contains('active')) continue;

    var rows = screen.querySelectorAll('.tkt-row');
    var total = 0;
    rows.forEach(function(row) {
      var price = parseInt(row.dataset.price);
      var qty = parseInt(row.querySelector('.tkt-counter-val').textContent);
      total += price * qty;
    });

    if (screens[s].hasCombo) {
      var comboVal = document.querySelector('.tkt-combo-counter-val');
      if (comboVal) total += parseInt(comboVal.textContent) * 4500;
    }

    var el = document.getElementById(screens[s].totalId);
    if (el) el.textContent = total > 0 ? formatPrice(total) + ' ₽' : '0 ₽';
    break;
  }
}

// === Combo quantity ===
function changeComboQty(btn, delta) {
  const valEl = btn.closest('.tkt-combo-counter').querySelector('.tkt-combo-counter-val');
  let val = parseInt(valEl.textContent) + delta;
  if (val < 0) val = 0;
  valEl.textContent = val;
  updateTicketsTotal();
}

// === Rental quantity ===
function changeRentalQty(btn, delta) {
  const counter = btn.closest('.rent-counter');
  const valueEl = counter.querySelector('.rent-counter-val');
  const row = btn.closest('.rent-qty-row');
  let val = parseInt(valueEl.textContent) + delta;
  if (val < 0) val = 0;
  valueEl.textContent = val;

  if (val > 0) {
    row.classList.add('rent-qty-row--selected');
  } else {
    row.classList.remove('rent-qty-row--selected');
  }

  updateRentalTotal();
}

function updateRentalTotal() {
  const rows = document.querySelectorAll('#screen-rental .rent-qty-row');
  let total = 0;
  rows.forEach(row => {
    const priceText = row.querySelector('.rent-qty-price').textContent;
    const price = parseInt(priceText.replace(/\s/g, '').replace('₽', ''));
    const qty = parseInt(row.querySelector('.rent-counter-val').textContent);
    total += price * qty;
  });
  const el = document.getElementById('rental-total');
  if (el) {
    el.textContent = total > 0 ? formatPrice(total) + ' ₽' : '0 ₽';
  }
}

function formatPrice(n) {
  return n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}

// === Ticket Carousels ===
document.querySelectorAll('[data-carousel]').forEach(function(carousel) {
  var track = carousel.querySelector('.tkt-carousel-track');
  var dotsWrap = carousel.querySelector('.tkt-carousel-dots');
  var slides = carousel.querySelectorAll('.tkt-carousel-slide');
  if (!track || !dotsWrap || slides.length === 0) return;

  // Generate dots
  slides.forEach(function(_, i) {
    var dot = document.createElement('button');
    dot.className = 'tkt-carousel-dot' + (i === 0 ? ' active' : '');
    dot.onclick = function() {
      slides[i].scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'start' });
    };
    dotsWrap.appendChild(dot);
  });

  // Hide dots if single slide
  if (slides.length <= 1) dotsWrap.style.display = 'none';

  // Track scroll position
  var dots = dotsWrap.querySelectorAll('.tkt-carousel-dot');
  track.addEventListener('scroll', function() {
    var scrollLeft = track.scrollLeft;
    var width = track.offsetWidth;
    var idx = Math.round(scrollLeft / width);
    dots.forEach(function(d, i) {
      d.classList.toggle('active', i === idx);
    });
  });
});

// === Clock ===
function updateClock() {
  const now = new Date();
  const time = now.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  document.querySelectorAll('.bottom-time').forEach(el => el.textContent = time);
}

updateClock();
setInterval(updateClock, 30000);

// === Auto-return to splash after inactivity ===
let inactivityTimer = null;
let inactivityCountdownTimer = null;
const INACTIVITY_TIMEOUT = 20000; // 20 seconds before warning
const INACTIVITY_COUNTDOWN = 10;  // 10 second countdown in modal

function resetInactivityTimer() {
  clearTimeout(inactivityTimer);
  clearInterval(inactivityCountdownTimer);
  hideInactivityModal();
  var splashEl = document.getElementById('screen-splash');
  if (splashEl && splashEl.classList.contains('active')) return;
  inactivityTimer = setTimeout(showInactivityModal, INACTIVITY_TIMEOUT);
}

function showInactivityModal() {
  var modal = document.getElementById('inactivity-modal');
  var countEl = document.getElementById('inactivity-countdown');
  if (!modal) return;
  var remaining = INACTIVITY_COUNTDOWN;
  if (countEl) countEl.textContent = remaining;
  modal.classList.add('active');

  clearInterval(inactivityCountdownTimer);
  inactivityCountdownTimer = setInterval(function() {
    remaining--;
    if (countEl) countEl.textContent = remaining;
    if (remaining <= 0) {
      clearInterval(inactivityCountdownTimer);
      hideInactivityModal();
      clearInterval(countdownInterval);
      clearTimeout(successTimer);
      clearInterval(sbpCountdownInterval);
      clearTimeout(sbpTimer);
      navigateTo('splash');
    }
  }, 1000);
}

function hideInactivityModal() {
  var modal = document.getElementById('inactivity-modal');
  if (modal) modal.classList.remove('active');
}

function dismissInactivity() {
  resetInactivityTimer();
}

function goToSplashNow() {
  clearTimeout(inactivityTimer);
  clearInterval(inactivityCountdownTimer);
  hideInactivityModal();
  clearInterval(countdownInterval);
  clearTimeout(successTimer);
  clearInterval(sbpCountdownInterval);
  clearTimeout(sbpTimer);
  navigateTo('splash');
}

document.addEventListener('click', function(e) {
  var modal = document.getElementById('inactivity-modal');
  if (modal && modal.classList.contains('active')) {
    if (e.target.closest('.inactivity-btn')) return;
    resetInactivityTimer();
    return;
  }
  resetInactivityTimer();
});
document.addEventListener('touchstart', function(e) {
  var modal = document.getElementById('inactivity-modal');
  if (modal && modal.classList.contains('active')) {
    if (e.target.closest('.inactivity-btn')) return;
    resetInactivityTimer();
    return;
  }
  resetInactivityTimer();
});
resetInactivityTimer();

// === Payment Processing ===
let successTimer = null;
let countdownInterval = null;
let sbpTimer = null;
let sbpCountdownInterval = null;
let paymentSourceScreen = null; // 'tickets' or 'rental'
let pendingCartItems = [];
let pendingCartTotal = 0;
let lastPaymentRRN = '';
let lastPaymentAuthCode = '';
let lastPaymentCardNumber = '';
let paymentAbortController = null;

// Collect selected items from any ticket screen
function collectTicketItems(screenId) {
  const items = [];
  document.querySelectorAll('#' + screenId + ' .tkt-row').forEach(row => {
    const qty = parseInt(row.querySelector('.tkt-counter-val').textContent);
    if (qty > 0) {
      const name = row.querySelector('.tkt-pill').textContent.trim();
      const price = parseInt(row.dataset.price);
      const tariffId = row.dataset.tariffId || null;
      items.push({ name: name, price: price, qty: qty, tariffId: tariffId });
    }
  });
  // Combo counter (only on tickets screen)
  if (screenId === 'screen-tickets') {
    const comboVal = document.querySelector('.tkt-combo-counter-val');
    if (comboVal) {
      const qty = parseInt(comboVal.textContent);
      if (qty > 0) {
        items.push({ name: 'Комбо: Канатная дорога + Парк Альпак', price: 4500, qty: qty });
      }
    }
  }
  return items;
}

// Collect selected items from rental screen
function collectRentalItems() {
  const items = [];
  document.querySelectorAll('#screen-rental .rent-qty-row').forEach(row => {
    const qty = parseInt(row.querySelector('.rent-counter-val').textContent);
    if (qty > 0) {
      const name = 'Прокат: ' + row.querySelector('.rent-qty-pill').textContent.trim();
      const price = parseInt(row.dataset.price);
      items.push({ name: name, price: price, qty: qty });
    }
  });
  return items;
}

// Calculate total from items
function calculateTotal(items) {
  return items.reduce(function(sum, item) {
    return sum + item.price * item.qty;
  }, 0);
}

// Step 1: User clicks ОПЛАТИТЬ → collect cart, show payment methods
function processPayment() {
  // Determine which screen is active
  var ticketScreens = ['tickets', 'alpaka', 'museum', 'skypark'];
  paymentSourceScreen = null;
  pendingCartItems = [];

  for (var i = 0; i < ticketScreens.length; i++) {
    var sid = 'screen-' + ticketScreens[i];
    var el = document.getElementById(sid);
    if (el && el.classList.contains('active')) {
      paymentSourceScreen = ticketScreens[i];
      pendingCartItems = collectTicketItems(sid);
      break;
    }
  }

  if (!paymentSourceScreen) {
    var rentalScreen = document.getElementById('screen-rental');
    if (rentalScreen && rentalScreen.classList.contains('active')) {
      paymentSourceScreen = 'rental';
      pendingCartItems = collectRentalItems();
    }
  }

  pendingCartTotal = calculateTotal(pendingCartItems);

  if (pendingCartItems.length === 0 || pendingCartTotal === 0) {
    showAlert('Выберите хотя бы один товар');
    return;
  }

  // Show total on payment screen
  const payTotalEl = document.getElementById('pay-total-value');
  if (payTotalEl) payTotalEl.textContent = formatPrice(pendingCartTotal) + ' ₽';

  // Populate order summary
  const orderItems = document.getElementById('pay-order-items');
  if (orderItems) {
    orderItems.innerHTML = '';
    pendingCartItems.forEach(function(item) {
      var row = document.createElement('div');
      row.className = 'pay-order-row';
      row.innerHTML = '<div class="pay-order-row-name"><span class="pay-order-dot"></span><span class="pay-order-row-label">' +
        item.name + ' × ' + item.qty + '</span></div><span class="pay-order-row-price">' +
        formatPrice(item.price * item.qty) + ' ₽</span>';
      orderItems.appendChild(row);
    });
  }

  navigateTo('payment');
  lucide.createIcons();
}

// Back from payment method screen
function goBackFromPayment() {
  hidePaymentLoader();
  if (paymentSourceScreen) {
    navigateTo(paymentSourceScreen);
  } else {
    navigateTo('main');
  }
}

function showPaymentLoader(text) {
  var loader = document.getElementById('payment-loader');
  var loaderText = loader ? loader.querySelector('.payment-loader-text') : null;
  if (loaderText) loaderText.textContent = text || 'Обработка оплаты...';
  if (loader) loader.classList.add('active');
}

function hidePaymentLoader() {
  var loader = document.getElementById('payment-loader');
  if (loader) loader.classList.remove('active');
}

// Step 2a: Pay by card (PAX S300 via INPAS DualConnector)
function payByCard() {
  var amountKopecks = pendingCartTotal * 100;
  var orderId = 'VG-' + Date.now().toString(36).toUpperCase();

  showPaymentLoader('Приложите карту к терминалу...');

  // AbortController for 130s timeout (DC timeout is 120s)
  paymentAbortController = new AbortController();
  var timeoutId = setTimeout(function() {
    paymentAbortController.abort();
  }, 130000);

  fetch('http://localhost:5050/api/pay', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal: paymentAbortController.signal,
    body: JSON.stringify({ amount: amountKopecks, order_id: orderId })
  })
  .then(function(response) { return response.json(); })
  .then(function(data) {
    clearTimeout(timeoutId);
    hidePaymentLoader();
    if (data.success) {
      lastPaymentRRN = data.rrn || '';
      lastPaymentAuthCode = data.authorization_code || '';
      lastPaymentCardNumber = data.card_number || '';
      completePayment('Банковская карта');
    } else {
      var errorMsg = data.message || data.error || 'Оплата отклонена';
      showAlert(errorMsg);
    }
  })
  .catch(function(err) {
    clearTimeout(timeoutId);
    hidePaymentLoader();
    if (err.name === 'AbortError') {
      showAlert('Время ожидания оплаты истекло');
    } else {
      console.error('[PAY] Error:', err);
      showAlert('Ошибка связи с терминалом оплаты');
    }
  });
}

// Step 2b: Pay by SBP — show QR code
function payBySBP() {
  // Show amount
  const sbpAmountEl = document.getElementById('sbp-amount-value');
  if (sbpAmountEl) sbpAmountEl.textContent = formatPrice(pendingCartTotal) + ' ₽';

  navigateTo('sbp');
  lucide.createIcons();

  // Generate SBP QR code (simulated payment URL)
  var sbpPaymentId = 'AD' + Date.now().toString(36).toUpperCase();
  var sbpUrl = 'https://qr.nspk.ru/' + sbpPaymentId + '?type=02&bank=&sum=' + (pendingCartTotal * 100) + '&cur=RUB&crc=0000';

  var canvas = document.getElementById('sbp-qr-canvas');
  if (canvas) {
    TicketService.renderQRToCanvas(canvas, sbpUrl, 280);
  }

  // Start SBP countdown (120 seconds)
  var remaining = 120;
  var countdownEl = document.getElementById('sbp-countdown');
  if (countdownEl) countdownEl.textContent = remaining;

  clearInterval(sbpCountdownInterval);
  clearTimeout(sbpTimer);

  sbpCountdownInterval = setInterval(function() {
    remaining--;
    if (countdownEl) countdownEl.textContent = remaining;
    if (remaining <= 0) {
      clearInterval(sbpCountdownInterval);
      showAlert('Время ожидания истекло');
      navigateTo('payment');
    }
  }, 1000);

  // Simulate successful payment after 8 seconds (for demo)
  sbpTimer = setTimeout(function() {
    clearInterval(sbpCountdownInterval);
    completePayment('СБП');
  }, 8000);
}

// Cancel SBP payment
function cancelSBP() {
  clearInterval(sbpCountdownInterval);
  clearTimeout(sbpTimer);
  navigateTo('payment');
}

// Step 2c: Free payment — immediate ticket
function payFree() {
  showPaymentLoader('Оформление билетов...');
  setTimeout(function() {
    hidePaymentLoader();
    completePayment('Без оплаты');
  }, 1500);
}

// Step 3: Complete payment — create individual tickets, show receipt modal
var pendingTickets = [];
var lastPaymentMethod = '';

function completePayment(paymentMethod) {
  lastPaymentMethod = paymentMethod;
  pendingTickets = [];

  // Create one ticket per item unit (e.g. qty=2 → 2 separate tickets)
  try {
    for (var i = 0; i < pendingCartItems.length; i++) {
      var item = pendingCartItems[i];
      for (var q = 0; q < item.qty; q++) {
        var singleItem = [{ name: item.name, price: item.price, qty: 1 }];
        var ticket = TicketService.createTicket(singleItem, item.price, paymentMethod);
        pendingTickets.push(ticket);
      }
    }
  } catch (e) {
    console.error('Ticket creation failed:', e);
    showAlert('Ошибка создания билета');
    return;
  }

  // Show success screen, print tickets, then ask about email receipt
  navigateTo('success');

  var printDone = false;
  function onPrintFinished() {
    if (printDone) return;
    printDone = true;
    hidePrintLoader();
    showReceiptInline();
  }

  showPrintLoader();
  printAllTickets(onPrintFinished);
  // Safety: if printing hangs, proceed after 6 seconds
  setTimeout(onPrintFinished, 6000);
}

// === Receipt (inline on success card) ===
function showReceiptInline() {
  var question = document.getElementById('success-receipt-question');
  var buttons = document.getElementById('success-receipt-buttons');
  var emailForm = document.getElementById('success-receipt-email');
  var emailInput = document.getElementById('receipt-email-input');

  if (question) question.style.display = '';
  if (buttons) buttons.style.display = 'flex';
  if (emailForm) emailForm.style.display = 'none';
  if (emailInput) emailInput.value = '';

  startSuccessCountdown();
  lucide.createIcons();
}

function receiptYes() {
  document.getElementById('success-receipt-question').style.display = 'none';
  document.getElementById('success-receipt-email').style.display = 'flex';
  document.getElementById('receipt-email-input').value = '';
  // Pause countdown while typing email
  clearInterval(countdownInterval);
  clearTimeout(successTimer);
}

function receiptNo() {
  goToMainFromSuccess();
}

function receiptBackToButtons() {
  document.getElementById('success-receipt-email').style.display = 'none';
  document.getElementById('success-receipt-question').style.display = '';
  startSuccessCountdown();
}

function receiptSendEmail() {
  var email = document.getElementById('receipt-email-input').value.trim();
  if (!email || email.indexOf('@') === -1 || email.indexOf('.') === -1) {
    showAlert('Введите корректный email');
    return;
  }
  console.log('[EMAIL RECEIPT] ' + email, pendingTickets.map(function(t) { return t.number; }));
  showAlert('Чек отправлен на ' + email);
  goToMainFromSuccess();
}

function goToMainFromSuccess() {
  clearInterval(countdownInterval);
  clearTimeout(successTimer);
  navigateTo('main');
}

// Print tickets one by one with delay between each
function showPrintLoader() {
  var loader = document.getElementById('print-loader');
  var countEl = document.getElementById('print-loader-count');
  if (countEl) countEl.textContent = '';
  if (loader) loader.classList.add('active');
}

function hidePrintLoader() {
  var loader = document.getElementById('print-loader');
  if (loader) loader.classList.remove('active');
}

function printAllTickets(onAllDone) {
  if (pendingTickets.length === 0) {
    if (onAllDone) onAllDone();
    return;
  }

  var total = pendingTickets.length;
  var countEl = document.getElementById('print-loader-count');

  function printNext(index) {
    if (index >= total) {
      var area = document.getElementById('print-area');
      if (area) area.innerHTML = '';
      if (onAllDone) onAllDone();
      return;
    }
    if (countEl) countEl.textContent = (index + 1) + ' из ' + total;
    try {
      TicketService.printTicket(pendingTickets[index], function() {
        printNext(index + 1);
      });
    } catch (e) {
      console.error('Ticket print failed:', e);
      printNext(index + 1);
    }
  }

  setTimeout(function() { printNext(0); }, 500);
}

// Success countdown
function startSuccessCountdown() {
  var remaining = 15;
  var countdownEl = document.getElementById('success-countdown');
  if (countdownEl) countdownEl.textContent = remaining;

  clearInterval(countdownInterval);
  clearTimeout(successTimer);

  countdownInterval = setInterval(function() {
    remaining--;
    if (countdownEl) countdownEl.textContent = remaining;
    if (remaining <= 0) {
      clearInterval(countdownInterval);
    }
  }, 1000);

  successTimer = setTimeout(function() {
    clearInterval(countdownInterval);
    goToMainFromSuccess();
  }, 15000);
}

// === Virtual Keyboard ===
document.addEventListener('click', function(e) {
  var key = e.target.closest('.vkb-key');
  if (!key) return;

  var input = document.getElementById('receipt-email-input');
  if (!input) return;

  var action = key.getAttribute('data-action');
  if (action === 'backspace') {
    input.value = input.value.slice(0, -1);
  } else {
    var ch = key.getAttribute('data-key');
    if (ch) input.value += ch;
  }
});

// === Banner Carousel ===
(function() {
  var track = document.getElementById('banner-track');
  var dotsContainer = document.getElementById('banner-dots');
  if (!track || !dotsContainer) return;

  var slides = track.querySelectorAll('.banner');
  var dots = dotsContainer.querySelectorAll('.banner-dot');
  var current = 0;
  var total = slides.length;
  var autoInterval = null;
  var AUTO_DELAY = 5000; // 5 seconds

  function goTo(index) {
    if (index < 0) index = total - 1;
    if (index >= total) index = 0;
    current = index;
    track.style.transform = 'translateX(-' + (current * 100) + '%)';
    dots.forEach(function(d, i) {
      d.classList.toggle('active', i === current);
    });
  }

  function startAuto() {
    stopAuto();
    autoInterval = setInterval(function() {
      goTo(current + 1);
    }, AUTO_DELAY);
  }

  function stopAuto() {
    clearInterval(autoInterval);
  }

  // Dot clicks
  dots.forEach(function(dot, i) {
    dot.addEventListener('click', function() {
      goTo(i);
      startAuto();
    });
  });

  // Touch swipe
  var startX = 0;
  var startY = 0;
  var isDragging = false;

  track.addEventListener('touchstart', function(e) {
    startX = e.touches[0].clientX;
    startY = e.touches[0].clientY;
    isDragging = true;
    stopAuto();
  }, { passive: true });

  track.addEventListener('touchmove', function(e) {
    if (!isDragging) return;
    var dx = e.touches[0].clientX - startX;
    var dy = e.touches[0].clientY - startY;
    // Prevent vertical scroll when swiping horizontally
    if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 10) {
      e.preventDefault();
    }
  }, { passive: false });

  track.addEventListener('touchend', function(e) {
    if (!isDragging) return;
    isDragging = false;
    var dx = e.changedTouches[0].clientX - startX;
    if (dx < -50) goTo(current + 1);   // swipe left
    else if (dx > 50) goTo(current - 1); // swipe right
    startAuto();
  }, { passive: true });

  // Mouse drag (for desktop testing)
  track.addEventListener('mousedown', function(e) {
    startX = e.clientX;
    isDragging = true;
    stopAuto();
    e.preventDefault();
  });

  document.addEventListener('mouseup', function(e) {
    if (!isDragging) return;
    isDragging = false;
    var dx = e.clientX - startX;
    if (dx < -50) goTo(current + 1);
    else if (dx > 50) goTo(current - 1);
    startAuto();
  });

  // Start auto-rotation
  startAuto();
})();
