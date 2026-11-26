// Página de inicio: dibuja la rejilla con datos.json (lo escribe inicio-datos cada 30 s), la hora y el fondo.
'use strict';

const $ = (id) => document.getElementById(id);
const crear = (etiqueta, clase, texto) => {
  const e = document.createElement(etiqueta);
  if (clase) e.className = clase;
  if (texto !== undefined) e.textContent = texto;
  return e;
};

// iconos de serie para los widgets (de trazo)
const ICONOS = {
  sai: '<rect x="3" y="7" width="16" height="10" rx="2"/><path d="M21 10v4"/><path d="M11 9l-2 4h4l-2 4"/>',
  nube: '<path d="M7 18a5 5 0 0 1-.6-9.96A6 6 0 0 1 18 9a4.5 4.5 0 0 1-.5 9z"/>',
  escudo: '<path d="M12 3l7 3v5c0 4.5-3 8.2-7 10-4-1.8-7-5.5-7-10V6z"/>',
  calendario: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
};
const icono = (nombre) => {
  if (ICONOS[nombre]) {
    const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    s.setAttribute('viewBox', '0 0 24 24');
    s.setAttribute('aria-hidden', 'true');
    s.innerHTML = ICONOS[nombre];
    return s;
  }
  const i = crear('img');
  i.src = 'icons/' + nombre;
  i.alt = '';
  return i;
};

// ---------- cifras ----------
const numero = (v, decimales = 0) =>
  v.toLocaleString('es-ES', { minimumFractionDigits: decimales, maximumFractionDigits: decimales });
const duracion = (s) =>
  s < 60 ? [Math.round(s), 's'] : s < 3600 ? [Math.round(s / 60), 'min'] : s < 86400 ? [Math.round(s / 3600), 'h'] : [numero(s / 86400, 1), 'd'];

const cifra = (c) => {
  const caja = crear('div', 'cifra');
  const v = crear('div', 'v');
  if (c.valor === null || c.valor === undefined) {
    v.textContent = '–';
  } else if (c.formato === 'duracion') {
    const [n, u] = duracion(c.valor);
    v.append(String(n), crear('small', '', u));
  } else {
    v.textContent = numero(c.valor, c.decimales ?? 0) + (c.de !== undefined ? '/' + (c.de === null ? '–' : numero(c.de)) : '');
    if (c.unidad) v.append(crear('small', '', c.unidad));
  }
  const r = c.rojo;
  if (r && c.valor !== null && ((r.mayor !== undefined && c.valor > r.mayor) || (r.menor !== undefined && c.valor < r.menor))) {
    v.classList.add('rojo');
  }
  caja.append(v, crear('div', 'l', c.etiqueta || ''));
  return caja;
};

// ---------- piezas de la rejilla ----------
// forma del icono: lleno (cuadrado que tapa la placa, como los de iOS), pixel (pixel-art) o glifo (centrado)
const FORMAS = ['lleno', 'pixel', 'glifo'];
const forma = (f) => (FORMAS.includes(f) ? f : 'glifo');

const app = (a, conTamano = true) => {
  const e = crear(a.url ? 'a' : 'div', 'app' + (conTamano ? ' t2x2' : ''));
  if (a.url) {
    e.href = a.url;
    e.target = '_blank';   // todo en otra pestaña (pedido por él): el inicio se queda abierto
    e.rel = 'noopener noreferrer';
  }
  const ic = crear('div', 'icono ' + forma(a.forma));
  if (a.icono) ic.append(icono(a.icono));
  if (a.arriba === true) ic.dataset.arriba = 'si';
  if (a.arriba === false) ic.dataset.arriba = 'no';
  e.append(ic, crear('div', 'nombre', a.nombre));
  if (a.arriba === false) e.title = a.nombre + ': no responde';
  return e;
};

const carpeta = (c) => {
  const b = crear('button', 'app carpeta t2x2');
  b.type = 'button';
  b.dataset.carpeta = c.carpeta;
  const ic = crear('div', 'icono');
  for (const a of c.apps.slice(0, 9)) {
    const m = crear('span', 'mini ' + forma(a.forma));
    if (a.icono) m.append(icono(a.icono));
    ic.append(m);
  }
  if (c.apps.some((a) => a.arriba === false)) ic.dataset.arriba = 'no';
  b.append(ic, crear('div', 'nombre', c.nombre));
  // detail 0 = teclado (Intro/espacio): solo entonces se lleva el foco dentro
  b.addEventListener('click', (e) => abrir(c.carpeta, e.detail === 0));
  return b;
};

// ---------- caducidades: fechas y días que quedan ----------
const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
const diasHasta = (ts) => Math.round((ts - Date.now() / 1000) / 86400);
// ámbar en el último mes (aviso a 30 días), rojo en la última semana (aviso a 7)
const claseDias = (d) => (d < 7 ? ' rojo' : d < 30 ? ' ambar' : '');
const fechaCorta = (ts) => {
  const f = new Date(ts * 1000);
  return `${f.getDate()} ${MESES[f.getMonth()]} ${f.getFullYear()}`;
};
const fechaLarga = (ts) => new Date(ts * 1000).toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' });
const quedan = (d, unidad) => {
  const v = crear('span');
  v.append(String(d), crear('small', '', unidad));
  return v;
};

// A · lista: las más cercanas (sin los grupos) y una línea con los grupos (certificados TLS)
const listaCaducidades = (c) => {
  const caja = crear('div', 'cad');
  const lista = crear('div', 'cad-lista');
  for (const f of c.filas.filter((f) => f.tipo !== 'grupo').slice(0, c.mostrar)) {
    const d = diasHasta(f.ts);
    const fila = crear('div', 'cad-fila');
    fila.title = f.completo || f.nombre;
    const dd = crear('div', 'd' + claseDias(d));
    dd.append(quedan(d, 'd'));
    fila.append(crear('div', 'n', f.nombre), crear('div', 'f', fechaCorta(f.ts)), dd);
    lista.append(fila);
  }
  caja.append(lista);
  for (const g of c.filas.filter((f) => f.tipo === 'grupo')) {
    caja.append(crear('div', 'cad-pie', `${g.nombre}${g.nota ? ' · ' + g.nota : ''} · el primero en ${diasHasta(g.ts)} d`));
  }
  return caja;
};

const TAMANOS = ['2x2', '3x2', '4x2', '6x2', '6x3'];
const widget = (w) => {
  const e = crear('div', 'widget t' + (TAMANOS.includes(w.tamano) ? w.tamano : '6x2'));
  const caja = crear('div', 'caja');
  const titulo = crear('div', 'titulo');
  if (w.icono) titulo.append(icono(w.icono));
  titulo.append(w.titulo || '');
  if (w.estado) titulo.append(crear('span', 'estado', '· ' + w.estado));
  if (w.ok !== undefined) {
    const p = crear('span', 'punto' + (w.ok ? '' : ' mal'));
    p.title = w.caducidades ? (w.ok ? 'Nada caduca en el próximo mes' : 'Algo caduca en menos de un mes') : (w.ok ? 'Todo bien' : 'Algo falla');
    titulo.append(p);
  }
  if (w.caducidades) {
    caja.append(titulo, listaCaducidades(w.caducidades));
    // se pulsa: vista completa con todo y cómo renovarlo
    e.classList.add('pulsable');
    e.tabIndex = 0;
    e.setAttribute('role', 'button');
    e.setAttribute('aria-label', (w.titulo || 'Caducidades') + ': ver todas');
    e.dataset.vista = w.widget;
    e.addEventListener('click', () => abrirVista(w.widget));
    e.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); abrirVista(w.widget, true); }
    });
  } else {
    const cifras = crear('div', 'cifras');
    cifras.append(...(w.cifras || []).map(cifra));
    caja.append(titulo, cifras);
  }
  e.append(caja, crear('div', 'nombre', w.titulo || ''));
  return e;
};

// ---------- carpeta abierta: crece desde su icono y vuelve a él al cerrar ----------
let datos = null;
let abierta = null;
let antesDeAbrir = null;
const quieto = matchMedia('(prefers-reduced-motion: reduce)');
const pintarCarpeta = () => {
  const c = datos && datos.elementos.find((e) => e.carpeta === abierta);
  if (!c) return cerrar();
  $('carpeta-titulo').textContent = c.nombre;
  $('carpeta-dentro').replaceChildren(...c.apps.map((a) => app(a, false)));
};
// transformación que lleva el panel abierto al sitio y tamaño del icono de la carpeta
const desdeIcono = () => {
  const icono = document.querySelector(`[data-carpeta="${CSS.escape(abierta || '')}"] .icono`);
  const panel = $('carpeta-panel');
  if (!icono) return 'scale(.6)';
  const a = icono.getBoundingClientRect();
  const b = panel.getBoundingClientRect();
  const s = a.width / b.width;
  const dx = a.left + a.width / 2 - (b.left + b.width / 2);
  const dy = a.top + a.height / 2 - (b.top + b.height / 2);
  return `translate(${dx}px, ${dy}px) scale(${s})`;
};
const abrir = (id, teclado = false) => {
  antesDeAbrir = document.activeElement;
  abierta = id;
  pintarCarpeta();
  const capa = $('carpeta');
  const panel = $('carpeta-panel');
  capa.hidden = false;
  if (!quieto.matches) {
    // primero en el sitio del icono, sin transición; en el siguiente fotograma, a su sitio
    panel.style.transition = 'none';
    panel.style.transform = desdeIcono();
    panel.style.opacity = '0';
    capa.classList.remove('abierta');
    panel.getBoundingClientRect();
    panel.style.transition = '';
    requestAnimationFrame(() => {
      capa.classList.add('abierta');
      panel.style.transform = '';
      panel.style.opacity = '';
    });
  } else {
    capa.classList.add('abierta');
  }
  if (teclado) $('carpeta-dentro').querySelector('a, [tabindex]')?.focus({ preventScroll: true });
};
const cerrar = () => {
  const capa = $('carpeta');
  const panel = $('carpeta-panel');
  if (capa.hidden) return;
  const fin = () => {
    capa.hidden = true;
    panel.style.transform = '';
    panel.style.opacity = '';
    abierta = null;
  };
  capa.classList.remove('abierta');
  if (quieto.matches) {
    fin();
  } else {
    panel.style.transform = desdeIcono();
    panel.style.opacity = '0';
    panel.addEventListener('transitionend', fin, { once: true });
    setTimeout(() => { if (!capa.hidden) fin(); }, 450);   // por si no llega el transitionend
  }
  antesDeAbrir?.focus?.({ preventScroll: true });
};
$('carpeta').addEventListener('click', (e) => { if (!e.target.closest('.panel')) cerrar(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && abierta) cerrar(); });

// ---------- vista completa de un widget (caducidades): crece desde su recuadro, como las carpetas ----------
let vistaAbierta = null;
let antesDeVista = null;
const desdeRecuadro = () => {
  const caja = document.querySelector(`[data-vista="${CSS.escape(vistaAbierta || '')}"] .caja`);
  const panel = $('vista-panel');
  if (!caja) return 'scale(.6)';
  const a = caja.getBoundingClientRect();
  const b = panel.getBoundingClientRect();
  const dx = a.left + a.width / 2 - (b.left + b.width / 2);
  const dy = a.top + a.height / 2 - (b.top + b.height / 2);
  return `translate(${dx}px, ${dy}px) scale(${a.width / b.width}, ${a.height / b.height})`;
};
const pintarVista = () => {
  const w = datos && datos.elementos.find((e) => e.widget === vistaAbierta);
  if (!w || !w.caducidades) return cerrarVista();
  const titulo = crear('h2');
  titulo.id = 'vista-titulo';
  titulo.append(icono(w.icono || 'calendario'), w.titulo || 'Caducidades');
  const boton = crear('button', 'cerrar', 'Cerrar');
  boton.type = 'button';
  boton.addEventListener('click', cerrarVista);
  titulo.append(boton);
  const tabla = crear('table', 'cad-tabla');
  const cab = crear('tr');
  for (const t of ['Qué', 'Caduca', 'Quedan', 'Cómo renovar']) cab.append(crear('th', '', t));
  tabla.append(cab);
  for (const f of w.caducidades.filas) {
    const d = diasHasta(f.ts);
    const tr = crear('tr', f.tipo === 'grupo' ? 'grupo' : '');
    const n = crear('td', 'n', f.nombre);
    if (f.completo && f.completo !== f.nombre) n.title = f.completo;
    if (f.tipo === 'dominio') n.append(crear('span', 'tipo', 'dominio'));
    if (f.tipo === 'grupo' && f.nota) n.append(crear('span', 'tipo', f.nota));
    const fecha = f.tipo === 'grupo' && f.hasta && f.hasta !== f.ts ? `${fechaCorta(f.ts)} – ${fechaCorta(f.hasta)}` : fechaLarga(f.ts);
    const dd = crear('td', 'd' + (f.tipo === 'grupo' ? '' : claseDias(d)));
    dd.append(quedan(d, d === 1 ? 'día' : 'días'));
    // lo que parece una orden (sin espacios raros) va como código
    const r = crear('td', 'r');
    if (f.renovar) r.append(/^(En WSL: )?[\w.-]+\.sh\b/.test(f.renovar) ? crear('code', '', f.renovar.replace(/^En WSL: /, '')) : crear('span', 'txt', f.renovar));
    tr.append(n, crear('td', 'f', fecha), dd, r);
    tabla.append(tr);
  }
  const sub = crear('p', 'sub', 'Aviso por MD al entrar en el último mes y en la última semana.');
  $('vista-panel').replaceChildren(titulo, sub, tabla);
};
const abrirVista = (id, teclado = false) => {
  antesDeVista = document.activeElement;
  vistaAbierta = id;
  pintarVista();
  const capa = $('vista');
  const panel = $('vista-panel');
  capa.hidden = false;
  if (!quieto.matches) {
    panel.style.transition = 'none';
    panel.style.transform = desdeRecuadro();
    panel.style.opacity = '0';
    capa.classList.remove('abierta');
    panel.getBoundingClientRect();
    panel.style.transition = '';
    requestAnimationFrame(() => {
      capa.classList.add('abierta');
      panel.style.transform = '';
      panel.style.opacity = '';
    });
  } else {
    capa.classList.add('abierta');
  }
  if (teclado) panel.querySelector('.cerrar')?.focus({ preventScroll: true });
};
const cerrarVista = () => {
  const capa = $('vista');
  const panel = $('vista-panel');
  if (capa.hidden) return;
  const fin = () => {
    capa.hidden = true;
    panel.style.transform = '';
    panel.style.opacity = '';
    vistaAbierta = null;
  };
  capa.classList.remove('abierta');
  if (quieto.matches) {
    fin();
  } else {
    panel.style.transform = desdeRecuadro();
    panel.style.opacity = '0';
    panel.addEventListener('transitionend', fin, { once: true });
    setTimeout(() => { if (!capa.hidden) fin(); }, 450);
  }
  antesDeVista?.focus?.({ preventScroll: true });
};
$('vista').addEventListener('click', (e) => { if (!e.target.closest('.panel')) cerrarVista(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && vistaAbierta) cerrarVista(); });

// ---------- datos ----------
const pintar = () => {
  document.title = datos.titulo;
  // dos zonas: en pantalla ancha, widgets a la izquierda y apps a la derecha; en estrecha se juntan (display: contents)
  const zonaWidgets = crear('div', 'zona zona-widgets');
  const zonaApps = crear('div', 'zona zona-apps');
  for (const e of datos.elementos) {
    if (e.widget) zonaWidgets.append(widget(e));
    else zonaApps.append(e.carpeta ? carpeta(e) : app(e));
  }
  $('rejilla').replaceChildren(zonaWidgets, zonaApps);
  const s = datos.sondas;
  const r = $('resumen');
  r.classList.toggle('mal', s.caidas.length > 0);
  r.textContent = s.caidas.length ? `No responde: ${s.caidas.join(', ')}` : `Todo en marcha · ${s.bien}/${s.total} sondas`;
  if (abierta) pintarCarpeta();
  if (vistaAbierta) pintarVista();
};

const avisar = (texto) => {
  $('aviso').hidden = !texto;
  $('aviso').textContent = texto || '';
};

let intervalo = 30;
const cargar = async () => {
  try {
    const r = await fetch('datos.json', { cache: 'no-store' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    datos = await r.json();
    intervalo = datos.intervalo || 30;
    pintar();
    const edad = Date.now() / 1000 - datos.generado;
    avisar(edad > intervalo * 4 ? `Datos de hace ${Math.round(edad / 60)} min: ¿está parado inicio-datos?` : '');
  } catch (e) {
    avisar('No se pueden leer los datos (' + e.message + ').');
  }
  setTimeout(cargar, intervalo * 1000);
};

// ---------- hora ----------
const reloj = () => {
  const ahora = new Date();
  $('hora').textContent = ahora.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
  $('fecha').textContent = ahora.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' });
};

// ---------- fondo: curvas de nivel (ruido Perlin 3D + marching squares), estático, morado → verde ----------
const fondo = (() => {
  const lienzo = $('fondo');
  const ctx = lienzo.getContext('2d');
  const p = new Uint8Array(512);
  {
    const b = [...Array(256).keys()];
    let s = 1337;
    for (let i = 255; i > 0; i--) {
      s = (s * 16807) % 2147483647;
      const j = s % (i + 1);
      [b[i], b[j]] = [b[j], b[i]];
    }
    for (let i = 0; i < 512; i++) p[i] = b[i & 255];
  }
  const fade = (t) => t * t * t * (t * (t * 6 - 15) + 10);
  const lerp = (a, b, t) => a + (b - a) * t;
  const grad = (h, x, y, z) => {
    h &= 15;
    const u = h < 8 ? x : y;
    const v = h < 4 ? y : h === 12 || h === 14 ? x : z;
    return ((h & 1) ? -u : u) + ((h & 2) ? -v : v);
  };
  const ruido = (x, y, z) => {
    const X = Math.floor(x) & 255, Y = Math.floor(y) & 255, Z = Math.floor(z) & 255;
    x -= Math.floor(x); y -= Math.floor(y); z -= Math.floor(z);
    const u = fade(x), v = fade(y), w = fade(z);
    const A = p[X] + Y, AA = p[A] + Z, AB = p[A + 1] + Z, B = p[X + 1] + Y, BA = p[B] + Z, BB = p[B + 1] + Z;
    return lerp(lerp(lerp(grad(p[AA], x, y, z), grad(p[BA], x - 1, y, z), u),
                     lerp(grad(p[AB], x, y - 1, z), grad(p[BB], x - 1, y - 1, z), u), v),
                lerp(lerp(grad(p[AA + 1], x, y, z - 1), grad(p[BA + 1], x - 1, y, z - 1), u),
                     lerp(grad(p[AB + 1], x, y - 1, z - 1), grad(p[BB + 1], x - 1, y - 1, z - 1), u), v), w);
  };
  const CELDA = 8, ESCALA = 0.0042, NIVELES = 16;

  return () => {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const ancho = innerWidth, alto = innerHeight;
    lienzo.width = ancho * dpr;
    lienzo.height = alto * dpr;
    const cols = Math.ceil(ancho / CELDA) + 1, filas = Math.ceil(alto / CELDA) + 1;
    const campo = new Float32Array(cols * filas);
    for (let j = 0; j < filas; j++) {
      for (let i = 0; i < cols; i++) {
        const x = i * CELDA * ESCALA, y = j * CELDA * ESCALA;
        campo[j * cols + i] = (ruido(x, y, 0.5) + 0.5 * ruido(x * 2.1, y * 2.1, 0.8)) * NIVELES;
      }
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, ancho, alto);
    ctx.beginPath();
    for (let j = 0; j < filas - 1; j++) {
      for (let i = 0; i < cols - 1; i++) {
        const a = campo[j * cols + i], b = campo[j * cols + i + 1];
        const c = campo[(j + 1) * cols + i + 1], d = campo[(j + 1) * cols + i];
        const x0 = i * CELDA, y0 = j * CELDA;
        for (let n = Math.ceil(Math.min(a, b, c, d)); n <= Math.max(a, b, c, d); n++) {
          const pts = [];
          if ((a < n) !== (b < n)) pts.push(x0 + CELDA * (n - a) / (b - a), y0);
          if ((b < n) !== (c < n)) pts.push(x0 + CELDA, y0 + CELDA * (n - b) / (c - b));
          if ((d < n) !== (c < n)) pts.push(x0 + CELDA * (n - d) / (c - d), y0 + CELDA);
          if ((a < n) !== (d < n)) pts.push(x0, y0 + CELDA * (n - a) / (d - a));
          for (let k = 0; k + 3 < pts.length; k += 4) {
            ctx.moveTo(pts[k], pts[k + 1]);
            ctx.lineTo(pts[k + 2], pts[k + 3]);
          }
        }
      }
    }
    const g = ctx.createLinearGradient(0, 0, ancho, alto * 0.3);
    g.addColorStop(0, 'rgba(153, 51, 255, .55)');
    g.addColorStop(0.45, 'rgba(140, 60, 255, .5)');
    g.addColorStop(0.62, 'rgba(70, 150, 200, .45)');
    g.addColorStop(1, 'rgba(60, 230, 130, .5)');
    ctx.strokeStyle = g;
    ctx.lineWidth = 1.1;
    ctx.stroke();
  };
})();

let esperaFondo;
addEventListener('resize', () => {
  clearTimeout(esperaFondo);
  esperaFondo = setTimeout(fondo, 150);
});

reloj();
setInterval(reloj, 15000);
fondo();
cargar();
