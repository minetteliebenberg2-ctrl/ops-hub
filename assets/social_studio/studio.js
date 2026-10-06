/* Poster studio.
   Everything is drawn straight onto a canvas at true pixel size, so what
   she saves is exactly 1080x1080 (or whichever size is picked). No screen
   grabbing, no scaling guesswork. */

const GREEN = '#21A94D';
const NAVY = '#1a1a1a';
const CHARCOAL = '#3a3a3a';
const GREY = '#f5f5f5';

/* The trading identity is not hardcoded here - Ops Hub reads it from
   Settings -> Business Settings via /api/brand. Blank fields are simply
   not drawn, so a footer with only a phone number still looks right. */
let PHONE = '';
let SITE = '';
let HANDLE = '';

const SIZES = [
  { id: 'square', label: 'Square 1080', w: 1080, h: 1080 },
  { id: 'vertical', label: 'Vertical 1080x1920', w: 1080, h: 1920 },
  { id: 'landscape', label: 'Landscape 1200x627', w: 1200, h: 627 }
];

const LAYOUTS = [
  { id: 'before_after', label: 'Before & after', slots: 2 },
  { id: 'showcase', label: 'Finished job', slots: 1 },
  { id: 'offer', label: 'Price / offer', slots: 1 },
  { id: 'tip', label: 'Tip', slots: 0 },
  { id: 'imported', label: 'Imported design', slots: 1 }
];

const FIELDS = {
  before_after: ['kicker', 'headline', 'body'],
  showcase: ['kicker', 'headline', 'body'],
  offer: ['kicker', 'headline', 'price', 'priceNote', 'body'],
  tip: ['kicker', 'headline', 'body'],
  imported: []
};

const LABELS = {
  kicker: 'Kicker (small green line)',
  headline: 'Headline',
  body: 'Body copy',
  price: 'Price',
  priceNote: 'Price note'
};

const state = {
  size: 'square',
  layout: 'before_after',
  logo: true,
  footer: true,
  text: {
    kicker: 'Location',
    headline: 'Your headline goes here',
    body: 'One or two lines of body copy.',
    price: 'R0 000',
    priceNote: 'Product or service description'
  },
  photos: [null, null]
};

let gallery = [];
let activeSlot = 0;
let hits = [];
let logoImage = null;

const canvas = document.getElementById('poster');
const ctx = canvas.getContext('2d');

/* ---------------------------------------------- helpers */

function esc(value) {
  return String(value == null ? '' : value);
}

function wrap(text, maxWidth, font) {
  ctx.font = font;
  const lines = [];
  esc(text).split('\n').forEach(paragraph => {
    const words = paragraph.split(/\s+/).filter(Boolean);
    if (!words.length) { lines.push(''); return; }
    let line = words[0];
    for (let i = 1; i < words.length; i++) {
      const next = line + ' ' + words[i];
      if (ctx.measureText(next).width > maxWidth) { lines.push(line); line = words[i]; }
      else { line = next; }
    }
    lines.push(line);
  });
  return lines;
}

function drawLines(lines, x, y, lineHeight, font, colour) {
  ctx.font = font;
  ctx.fillStyle = colour;
  ctx.textBaseline = 'alphabetic';
  lines.forEach((line, i) => ctx.fillText(line, x, y + i * lineHeight));
  return y + lines.length * lineHeight;
}

/* Draw an image cropped to fill a box, centred - never squashed. */
function drawCover(image, x, y, w, h) {
  const scale = Math.max(w / image.width, h / image.height);
  const dw = image.width * scale;
  const dh = image.height * scale;
  ctx.save();
  ctx.beginPath();
  ctx.rect(x, y, w, h);
  ctx.clip();
  ctx.drawImage(image, x + (w - dw) / 2, y + (h - dh) / 2, dw, dh);
  ctx.restore();
}

function drawPlaceholder(x, y, w, h, label, unit) {
  ctx.fillStyle = GREY;
  ctx.fillRect(x, y, w, h);
  ctx.fillStyle = GREEN;
  ctx.fillRect(x, y, Math.max(3, 4 * unit), h);
  ctx.fillStyle = '#9a9a9a';
  ctx.font = (22 * unit) + 'px Archivo, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(label, x + w / 2, y + h / 2);
  ctx.textAlign = 'left';
  ctx.textBaseline = 'alphabetic';
}

/* A small green tag in the corner of a photo - "Before" / "After". */
function drawTag(x, y, label, unit) {
  const size = Math.round(22 * unit);
  const padX = Math.round(14 * unit);
  const padY = Math.round(9 * unit);
  ctx.font = '700 ' + size + 'px Archivo, sans-serif';
  const w = ctx.measureText(label).width + padX * 2;
  const h = size + padY * 2;
  ctx.fillStyle = GREEN;
  ctx.fillRect(x, y, w, h);
  ctx.fillStyle = '#ffffff';
  ctx.textBaseline = 'middle';
  ctx.fillText(label, x + padX, y + h / 2 + 1);
  ctx.textBaseline = 'alphabetic';
}

function slot(index, x, y, w, h, label, unit, tag) {
  const image = state.photos[index];
  if (image) {
    drawCover(image, x, y, w, h);
    // The placeholder says "Before"; once a photo lands the poster still has to.
    if (tag) drawTag(x, y, tag, unit);
  } else {
    drawPlaceholder(x, y, w, h, label, unit);
  }
  hits.push({ x: x, y: y, w: w, h: h, kind: 'photo', slot: index });
}

function textHit(x, y, w, h, field) {
  hits.push({ x: x, y: y, w: w, h: h, kind: 'text', field: field });
}

/* ---------------------------------------------- render */

function render() {
  const size = SIZES.find(s => s.id === state.size);
  const W = size.w;
  const H = size.h;
  canvas.width = W;
  canvas.height = H;

  const unit = W / 1080;
  const margin = Math.round(58 * unit);
  hits = [];

  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, W, H);

  if (state.layout === 'imported') {
    renderImported(W, H, unit, margin);
    return;
  }

  const bar = Math.max(4, Math.round(12 * unit));
  ctx.fillStyle = GREEN;
  ctx.fillRect(0, 0, W, bar);

  const footerHeight = state.footer ? Math.round(H * 0.075) : 0;
  let y = bar + margin * 0.75;

  /* logo */
  if (state.logo && logoImage) {
    const logoWidth = Math.round(W * 0.30);
    const logoHeight = logoWidth * (logoImage.height / logoImage.width);
    ctx.drawImage(logoImage, margin, y, logoWidth, logoHeight);
    y += logoHeight + Math.round(26 * unit);
  }

  /* kicker */
  const kicker = state.text.kicker.trim();
  if (kicker) {
    const font = '500 ' + Math.round(26 * unit) + 'px Archivo, sans-serif';
    ctx.font = font;
    const width = ctx.measureText(kicker).width;
    y = drawLines([kicker], margin, y + Math.round(22 * unit), 0, font, GREEN);
    textHit(margin, y - Math.round(26 * unit), width, Math.round(32 * unit), 'kicker');
  }

  /* headline */
  const headlineSize = Math.round((state.size === 'landscape' ? 52 : 62) * unit);
  const headlineFont = '700 ' + headlineSize + 'px Archivo, sans-serif';
  const headlineLines = wrap(state.text.headline, W - margin * 2, headlineFont);
  const headlineTop = y + Math.round(18 * unit);
  y = drawLines(headlineLines, margin, headlineTop + headlineSize, headlineSize * 1.12,
                headlineFont, NAVY);
  textHit(margin, headlineTop, W - margin * 2, y - headlineTop, 'headline');

  /* body copy sits just above the footer */
  const bodySize = Math.round(28 * unit);
  const bodyFont = '400 ' + bodySize + 'px Archivo, sans-serif';
  // On a tip the body is the point, so it goes inside the card instead.
  const bodyInCard = state.layout === 'tip';
  const bodyLines = (!bodyInCard && state.text.body.trim())
    ? wrap(state.text.body, W - margin * 2, bodyFont) : [];
  const bodyBlock = bodyLines.length * bodySize * 1.4;
  const bodyTop = H - footerHeight - margin * 0.7 - bodyBlock;

  /* the picture area is whatever is left between headline and body */
  const areaTop = y + Math.round(6 * unit);
  const areaBottom = bodyLines.length ? bodyTop - Math.round(26 * unit)
                                      : H - footerHeight - margin * 0.7;
  const areaHeight = Math.max(Math.round(80 * unit), areaBottom - areaTop);
  const areaWidth = W - margin * 2;

  if (state.layout === 'before_after') {
    const gap = Math.round(16 * unit);
    if (state.size === 'vertical') {
      const each = (areaHeight - gap) / 2;
      slot(0, margin, areaTop, areaWidth, each, 'Before', unit, 'Before');
      slot(1, margin, areaTop + each + gap, areaWidth, each, 'After', unit, 'After');
    } else {
      const each = (areaWidth - gap) / 2;
      slot(0, margin, areaTop, each, areaHeight, 'Before', unit, 'Before');
      slot(1, margin + each + gap, areaTop, each, areaHeight, 'After', unit, 'After');
    }
  } else if (state.layout === 'showcase') {
    slot(0, margin, areaTop, areaWidth, areaHeight, 'Photo', unit);
  } else if (state.layout === 'offer') {
    const gap = Math.round(20 * unit);
    const cardWidth = state.size === 'landscape' ? Math.round(areaWidth * 0.42)
                                                 : Math.round(areaWidth * 0.38);
    slot(0, margin, areaTop, areaWidth - cardWidth - gap, areaHeight, 'Photo', unit);
    drawPriceCard(margin + areaWidth - cardWidth, areaTop, cardWidth, areaHeight, unit);
  } else if (state.layout === 'tip') {
    drawTipCard(margin, areaTop, areaWidth, areaHeight, unit);
  }

  if (bodyLines.length) {
    drawLines(bodyLines, margin, bodyTop + bodySize, bodySize * 1.4, bodyFont, CHARCOAL);
    textHit(margin, bodyTop, areaWidth, bodyBlock, 'body');
  }

  if (state.footer) drawFooter(W, H, footerHeight, margin, unit);
}

function drawPriceCard(x, y, w, h, unit) {
  ctx.fillStyle = GREY;
  ctx.fillRect(x, y, w, h);
  ctx.fillStyle = GREEN;
  ctx.fillRect(x, y, w, Math.max(3, 6 * unit));

  const pad = Math.round(22 * unit);
  const priceSize = Math.round(58 * unit);
  const priceFont = '700 ' + priceSize + 'px Archivo, sans-serif';
  const priceLines = wrap(state.text.price, w - pad * 2, priceFont);
  let cursor = y + pad + priceSize + Math.round(10 * unit);
  cursor = drawLines(priceLines, x + pad, cursor, priceSize * 1.1, priceFont, NAVY);
  textHit(x + pad, y + pad, w - pad * 2, priceSize * 1.2 * priceLines.length, 'price');

  const noteSize = Math.round(24 * unit);
  const noteFont = '400 ' + noteSize + 'px Archivo, sans-serif';
  const noteLines = wrap(state.text.priceNote, w - pad * 2, noteFont);
  const noteTop = cursor + Math.round(8 * unit);
  drawLines(noteLines, x + pad, noteTop + noteSize, noteSize * 1.35, noteFont, CHARCOAL);
  textHit(x + pad, noteTop, w - pad * 2, noteLines.length * noteSize * 1.35, 'priceNote');
}

function drawTipCard(x, y, w, maxHeight, unit) {
  const pad = Math.round(40 * unit);
  const size = Math.round(38 * unit);
  const font = '400 ' + size + 'px Archivo, sans-serif';
  const lines = wrap(state.text.body, w - pad * 2, font);
  const lineHeight = size * 1.45;
  // Fit the card to the words, not to whatever space happens to be left.
  const height = Math.min(maxHeight, pad * 2 + lines.length * lineHeight);
  // Sit the card in the middle of the space rather than leaving a hole beneath it.
  y = y + Math.max(0, (maxHeight - height) / 2);

  ctx.fillStyle = GREY;
  ctx.fillRect(x, y, w, height);
  ctx.fillStyle = GREEN;
  ctx.fillRect(x, y, Math.max(3, 8 * unit), height);

  drawLines(lines, x + pad, y + pad + size, lineHeight, font, CHARCOAL);
  textHit(x + pad, y + pad, w - pad * 2, lines.length * lineHeight, 'body');
}

function drawFooter(W, H, height, margin, unit) {
  const top = H - height;
  ctx.fillStyle = NAVY;
  ctx.fillRect(0, top, W, height);

  const size = Math.round(24 * unit);
  ctx.font = '500 ' + size + 'px Archivo, sans-serif';
  ctx.fillStyle = '#f5f5f5';
  ctx.textBaseline = 'middle';
  if (PHONE) ctx.fillText(PHONE, margin, top + height / 2);

  ctx.textAlign = 'right';
  ctx.fillStyle = GREEN;
  if (HANDLE) ctx.fillText(HANDLE, W - margin, top + height / 2);

  ctx.textAlign = 'center';
  ctx.fillStyle = '#f5f5f5';
  if (SITE) ctx.fillText(SITE, W / 2, top + height / 2);

  ctx.textAlign = 'left';
  ctx.textBaseline = 'alphabetic';
}

function renderImported(W, H, unit, margin) {
  const image = state.photos[0];
  if (image) drawCover(image, 0, 0, W, H);
  else drawPlaceholder(0, 0, W, H, 'Click to load your design', unit);
  hits.push({ x: 0, y: 0, w: W, h: H, kind: 'photo', slot: 0 });

  if (state.logo && logoImage) {
    const logoWidth = Math.round(W * 0.26);
    const logoHeight = logoWidth * (logoImage.height / logoImage.width);
    const pad = Math.round(20 * unit);
    ctx.fillStyle = 'rgba(255,255,255,0.92)';
    ctx.fillRect(margin - pad, margin - pad, logoWidth + pad * 2, logoHeight + pad * 2);
    ctx.drawImage(logoImage, margin, margin, logoWidth, logoHeight);
  }

  if (state.footer) drawFooter(W, H, Math.round(H * 0.075), margin, unit);
}

/* ---------------------------------------------- rail */

function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

function buildPickers() {
  const sizes = document.getElementById('sizes');
  clear(sizes);
  SIZES.forEach(size => {
    const button = document.createElement('button');
    button.className = 'pick' + (size.id === state.size ? ' on' : '');
    button.textContent = size.label;
    button.onclick = () => { state.size = size.id; buildPickers(); render(); };
    sizes.appendChild(button);
  });

  const layouts = document.getElementById('layouts');
  clear(layouts);
  LAYOUTS.forEach(layout => {
    const button = document.createElement('button');
    button.className = 'pick' + (layout.id === state.layout ? ' on' : '');
    button.textContent = layout.label;
    button.onclick = () => { state.layout = layout.id; buildPickers(); buildFields(); render(); };
    layouts.appendChild(button);
  });
}

function buildFields() {
  const host = document.getElementById('fields');
  clear(host);

  const names = FIELDS[state.layout] || [];
  if (!names.length) {
    const note = document.createElement('p');
    note.className = 'note';
    note.textContent = 'An imported design carries its own text. Only the branding options below apply.';
    host.appendChild(note);
    return;
  }

  names.forEach(name => {
    const wrapper = document.createElement('div');
    wrapper.className = 'field';

    const label = document.createElement('label');
    label.textContent = LABELS[name];
    label.setAttribute('for', 'f-' + name);
    wrapper.appendChild(label);

    const isLong = (name === 'body');
    const input = document.createElement(isLong ? 'textarea' : 'input');
    if (!isLong) input.type = 'text';
    else input.rows = 3;
    input.id = 'f-' + name;
    input.value = state.text[name] || '';
    input.oninput = () => { state.text[name] = input.value; render(); };
    wrapper.appendChild(input);

    host.appendChild(wrapper);
  });
}

/* ---------------------------------------------- picking photos */

function openChooser(slotIndex) {
  activeSlot = slotIndex;
  document.getElementById('chooser').classList.remove('hidden');
  document.getElementById('chooser-title').textContent =
    state.layout === 'imported' ? 'Load a design' : 'Choose a photo';
  paintGallery(document.getElementById('gallery-search').value);
}

function closeChooser() {
  document.getElementById('chooser').classList.add('hidden');
}

function paintGallery(filter) {
  const grid = document.getElementById('gallery-grid');
  const empty = document.getElementById('gallery-empty');
  clear(grid);

  const needle = (filter || '').trim().toLowerCase();
  const matches = gallery.filter(item => {
    if (!needle) return true;
    return (item.customer + ' ' + item.album + ' ' + item.caption).toLowerCase().indexOf(needle) >= 0;
  });

  if (!gallery.length) {
    empty.textContent = 'No photos in the Gallery yet. Use "Browse my files" instead.';
  } else if (!matches.length) {
    empty.textContent = 'Nothing matches that.';
  } else {
    empty.textContent = '';
  }

  matches.forEach(item => {
    const tile = document.createElement('div');
    tile.className = 'thumb';

    const image = document.createElement('img');
    image.loading = 'lazy';
    image.src = '/photo/' + item.index;
    image.alt = item.caption || item.customer;
    tile.appendChild(image);

    const caption = document.createElement('span');
    caption.textContent = item.caption || item.customer;
    caption.title = item.customer + (item.album ? ' - ' + item.album : '');
    tile.appendChild(caption);

    tile.onclick = () => usePhoto('/photo/' + item.index);
    grid.appendChild(tile);
  });
}

function usePhoto(src) {
  const image = new Image();
  image.onload = () => { state.photos[activeSlot] = image; closeChooser(); render(); };
  image.onerror = () => { alert('That picture could not be loaded.'); };
  image.src = src;
}

/* ---------------------------------------------- saving */

function defaultName() {
  const headline = state.layout === 'imported' ? 'Imported design' : state.text.headline;
  const stamp = new Date().toISOString().slice(0, 10);
  return (headline || 'Poster').slice(0, 40) + ' ' + state.size + ' ' + stamp;
}

async function save() {
  const nameField = document.getElementById('filename');
  const stem = nameField.value.trim() || defaultName();
  const saved = document.getElementById('saved');
  saved.textContent = 'Saving...';

  try {
    const response = await fetch('/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ png: canvas.toDataURL('image/png'), name: stem })
    });
    const result = await response.json();
    if (result.ok) {
      saved.textContent = 'Saved to ' + result.path;
      saved.dataset.path = result.path;
    } else {
      saved.textContent = 'Could not save: ' + (result.error || 'unknown problem');
    }
  } catch (error) {
    saved.textContent = 'Could not save: ' + error.message;
  }
}

/* ---------------------------------------------- wiring */

function hitAt(clientX, clientY) {
  const box = canvas.getBoundingClientRect();
  const x = (clientX - box.left) * (canvas.width / box.width);
  const y = (clientY - box.top) * (canvas.height / box.height);
  for (let i = hits.length - 1; i >= 0; i--) {
    const hit = hits[i];
    if (x >= hit.x && x <= hit.x + hit.w && y >= hit.y && y <= hit.y + hit.h) return hit;
  }
  return null;
}

canvas.addEventListener('click', event => {
  const hit = hitAt(event.clientX, event.clientY);
  if (!hit) return;
  if (hit.kind === 'photo') { openChooser(hit.slot); return; }
  const field = document.getElementById('f-' + hit.field);
  if (field) { field.focus(); field.select(); }
});

document.getElementById('opt-logo').onchange = e => { state.logo = e.target.checked; render(); };
document.getElementById('opt-footer').onchange = e => { state.footer = e.target.checked; render(); };
document.getElementById('btn-save').onclick = save;
document.getElementById('chooser-close').onclick = closeChooser;
document.getElementById('gallery-search').oninput = e => paintGallery(e.target.value);

document.getElementById('btn-clear').onclick = () => {
  state.photos[activeSlot] = null;
  closeChooser();
  render();
};

document.getElementById('btn-browse').onclick = () => document.getElementById('file-input').click();

document.getElementById('file-input').onchange = event => {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => usePhoto(reader.result);
  reader.readAsDataURL(file);
  event.target.value = '';
};

document.getElementById('btn-folder').onclick = () => {
  const saved = document.getElementById('saved');
  fetch('/api/open-folder', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: saved.dataset.path || '' })
  });
};

document.getElementById('btn-meta').onclick =
  () => window.open('https://business.facebook.com/latest/composer', '_blank');
document.getElementById('btn-tiktok').onclick =
  () => window.open('https://www.tiktok.com/tiktokstudio/upload', '_blank');

/* ---------------------------------------------- boot */

async function boot() {
  try {
    gallery = await (await fetch('/api/gallery')).json();
  } catch (error) {
    gallery = [];
  }

  try {
    const b = await (await fetch('/api/brand')).json();
    PHONE = b.phone || '';
    SITE = b.site || '';
    HANDLE = b.handle || '';
    if (b.name) document.title = b.name + ' - Poster Studio';
  } catch (error) {
    /* no business settings yet - the footer just carries no contact line */
  }

  logoImage = new Image();
  logoImage.onload = render;
  logoImage.onerror = () => { logoImage = null; render(); };
  logoImage.src = '/logo.png';

  buildPickers();
  buildFields();

  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(render);
  }
  render();
}

boot();
