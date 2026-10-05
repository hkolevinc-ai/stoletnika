/* Runs only on stoletnika.eu. Reads public catalog pages and downloads a local file. */
void (async function () {
  'use strict';
  if (location.origin !== 'https://stoletnika.eu') {
    alert('Отвори https://stoletnika.eu/vendor/herbalkan и натисни бутона там.');
    return;
  }
  if (document.getElementById('stoletnika-export-panel')) return;
  const scopes = [
    'https://stoletnika.eu/vendor/bilka-chudodeyka',
    'https://stoletnika.eu/vendor/herbalkan',
    'https://stoletnika.eu/category/hranitelni-dobavki?vendors=natural-factors,webber-naturals'
  ];
  const host = document.createElement('div');
  host.id = 'stoletnika-export-panel';
  host.style.cssText = 'position:fixed;right:18px;top:18px;z-index:2147483647;max-width:430px;width:calc(100% - 36px)';
  document.body.appendChild(host);
  const panel = host.attachShadow({mode: 'open'});
  panel.innerHTML = `<style>
    :host{font:14px Arial,sans-serif;color:#172536}section{background:#fff;border:2px solid #245a76;border-radius:12px;padding:20px;box-shadow:0 8px 40px #0005}
    h2{font-size:20px;margin:0 0 12px}p{line-height:1.5}button{padding:10px 13px;margin:5px 5px 5px 0;cursor:pointer;border:1px solid #245a76;border-radius:6px;background:#245a76;color:white;font:inherit}
    button:disabled{opacity:.45;cursor:default}button.secondary{background:white;color:#245a76}progress{width:100%}a{color:#245a76;overflow-wrap:anywhere}small{display:block;line-height:1.5}#message{white-space:pre-wrap;overflow-wrap:anywhere}
    </style><section><h2>Stoletnika → Temu</h2><p>Извличане на трите избрани категории. Остави този таб отворен.</p>
    <progress id="progress" value="0" max="1"></progress><p id="message">Зареждане на запазения напредък…</p>
    <button id="start" disabled>Старт / Продължи</button><button id="pause" class="secondary" disabled>Пауза</button>
    <button id="download" disabled>Изтегли каталога</button><button id="reset" class="secondary" disabled>Ново сканиране</button>
    <small id="note">Напредъкът се пази в този Chrome. При HTTP 403 сканирането спира.</small><p><a id="failed" hidden target="_blank" rel="noopener">Отвори страницата с отказан достъп</a></p>
    <button id="close" class="secondary">Затвори панела</button></section>`;
  const $ = id => panel.getElementById(id);
  const db = await new Promise((resolve, reject) => {
    const request = indexedDB.open('stoletnika-temu-export-v1', 2);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains('state')) request.result.createObjectStore('state');
      if (!request.result.objectStoreNames.contains('pages')) request.result.createObjectStore('pages', {keyPath:'url'});
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
  async function readState() {
    const read = (store, all) => new Promise((resolve, reject) => {
      const request = all ? db.transaction(store).objectStore(store).getAll() : db.transaction(store).objectStore(store).get('catalog');
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    const [metadata, pages] = await Promise.all([read('state', false), read('pages', true)]);
    return metadata ? {...metadata, items:metadata.items || pages.map(row=>row.entry)} : null;
  }
  function persist() {
    return new Promise((resolve, reject) => {
      const tx = db.transaction(['state','pages'], 'readwrite');
      const {items,...metadata} = state;
      tx.objectStore('state').put(metadata, 'catalog');
      const entry = items.at(-1);
      if (entry) tx.objectStore('pages').put({url:entry.item.url,entry});
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error || new Error('Неуспешно запазване на напредъка'));
    });
  }
  const emptyState = () => ({format:'stoletnika-browser-export',version:1,started_at:new Date().toISOString(),complete:false,scopes:[],links:[],items:[],discovered_products:0,discovery_complete:false});
  let state = await readState() || emptyState();
  let running = false, stop = false;
  const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
  function show(text) {
    $('message').textContent = text;
    $('progress').max = state.discovered_products || 1;
    $('progress').value = state.items.length;
    $('start').disabled = running || state.complete;
    $('pause').disabled = !running;
    $('reset').disabled = running;
    $('download').disabled = running || !state.complete;
  }
  async function get(url) {
    const parsed = new URL(url);
    if (parsed.origin !== location.origin) throw new Error('Адрес извън Stoletnika');
    const response = await fetch(url, {credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(45000)});
    if (!response.ok) throw new Error('HTTP ' + response.status + ': ' + url);
    return new DOMParser().parseFromString(await response.text(), 'text/html');
  }
  function pageUrl(scope, number) {
    const url = new URL(scope);
    if (number > 1) url.searchParams.set('page', String(number));
    return url.href;
  }
  function pageCount(doc, scope) {
    const root = new URL(scope);
    let max = 1;
    for (const anchor of doc.querySelectorAll('a[href]')) {
      const url = new URL(anchor.getAttribute('href'), scope);
      if (url.origin !== root.origin || url.pathname !== root.pathname) continue;
      const wanted = root.searchParams.get('vendors');
      const actual = url.searchParams.get('vendors');
      if (wanted && actual && wanted !== actual) continue;
      const page = Number(url.searchParams.get('page') || 1);
      if (Number.isInteger(page) && page > 0 && page <= 200) max = Math.max(max, page);
    }
    return max;
  }
  function listing(doc, scope) {
    const result = [];
    for (const tile of doc.querySelectorAll('._product')) {
      const anchor = tile.querySelector('._product-name-tag a');
      if (!anchor) continue;
      const url = new URL(anchor.getAttribute('href'), scope);
      if (url.origin !== location.origin || !url.pathname.startsWith('/product/')) continue;
      url.search = ''; url.hash = '';
      result.push({url:url.href,id:tile.getAttribute('data-product-id'),name:anchor.textContent.trim().replace(/\s+/g,' '),scope,listing_price:tile.querySelector('._product-price')?.textContent.trim() || ''});
    }
    if (!result.length) throw new Error('Не е намерен каталог: ' + scope);
    return result;
  }
  function compact(doc, item) {
    const scripts = [...doc.querySelectorAll('script')].filter(node => /window\.cc_page_data\s*=/.test(node.textContent));
    if (!scripts.length) throw new Error('Продуктовите данни не са заредени: ' + item.url);
    const out = ['<html><body>', ...scripts.map(node => node.outerHTML)];
    for (const node of doc.querySelectorAll('script[type="application/ld+json"]')) {
      try { if (JSON.parse(node.textContent)['@type'] === 'Product') out.push(node.outerHTML); } catch (_) {}
    }
    const description = doc.getElementById('product-details-description');
    if (description) out.push(description.outerHTML);
    const detail = [...doc.querySelectorAll('[data-variant-selection]')].find(node => node.getAttribute('data-product-id') === item.id);
    if (detail) {
      const node = doc.createElement('div');
      node.setAttribute('data-product-id', item.id);
      node.setAttribute('data-variant-selection', detail.getAttribute('data-variant-selection'));
      out.push(node.outerHTML);
    }
    const images = new Set();
    for (const node of doc.querySelectorAll('a,img')) {
      for (const name of ['data-zoom-image','data-src','data-first-src','src','href']) {
        const value = node.getAttribute(name);
        if (value?.includes('/products/' + item.id + '/')) images.add(value);
      }
    }
    for (const value of images) {const node=doc.createElement('img');node.setAttribute('src',value);out.push(node.outerHTML);}
    out.push('</body></html>');
    return out.join('\n');
  }
  async function discover() {
    const seen = new Set(), links = [], stats = [];
    for (const scope of scopes) {
      if (stop) return false;
      show('Обхождам категория:\n' + scope);
      const first = await get(scope), pages = pageCount(first, scope);
      let count = 0;
      for (let number = 1; number <= pages; number++) {
        if (stop) return false;
        const doc = number === 1 ? first : await get(pageUrl(scope, number));
        const items = listing(doc, scope); count += items.length;
        for (const item of items) if (!seen.has(item.url)) {seen.add(item.url);links.push(item);}
        show('Категория ' + (stats.length + 1) + '/3, страница ' + number + '/' + pages + '\nОткрити продукти: ' + links.length);
        await delay(900);
      }
      stats.push({scope,pages,listing_rows:count});
    }
    state.links = links; state.scopes = stats; state.discovered_products = links.length; state.discovery_complete = true;
    await persist();
    return true;
  }
  $('start').onclick = async () => {
    if (running) return;
    running = true; stop = false; $('failed').hidden = true;
    let current = '';
    try {
      show('Започвам…');
      if (!state.discovery_complete && !await discover()) return;
      const done = new Set(state.items.map(entry => entry.item.url));
      for (const item of state.links) {
        if (stop) break;
        if (done.has(item.url)) continue;
        current = item.url;
        show('Продукти: ' + state.items.length + '/' + state.discovered_products + '\n' + item.name);
        const html = compact(await get(item.url), item);
        state.items.push({item,html,fetched_at:new Date().toISOString()});
        await persist();
        await delay(900);
      }
      state.complete = state.discovery_complete && state.items.length === state.discovered_products;
      if (state.complete) state.finished_at = new Date().toISOString();
      await persist();
    } catch (error) {
      show('Сканирането спря:\n' + error.message + '\nЗапазени продукти: ' + state.items.length + '/' + state.discovered_products);
      if (current) {$('failed').href = current; $('failed').hidden = false;}
      $('note').textContent = 'Достъпът е отказан или страницата не е заредена. Запазеният напредък остава. Продължи след като сайтът е достъпен в този Chrome.';
      console.error(error);
      return;
    } finally {
      running = false;
      if (state.complete) show('Готово: ' + state.items.length + ' продукта. Натисни „Изтегли каталога“.');
      else show($('message').textContent + '\nМожеш да продължиш от запазения напредък.');
    }
  };
  $('pause').onclick = () => {stop = true; $('pause').disabled=true; $('note').textContent='Пауза след текущата страница. Напредъкът ще бъде запазен.';};
  $('reset').onclick = async () => {
    if (!confirm('Да започна ново сканиране? Запазеният напредък ще бъде заменен.')) return;
    state = emptyState();
    await new Promise((resolve,reject)=>{const tx=db.transaction('pages','readwrite');tx.objectStore('pages').clear();tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);});
    await persist(); $('failed').hidden=true; show('Готово за ново сканиране.');
  };
  $('download').onclick = async () => {
    try {
      const data = {...state}; delete data.links; delete data.discovery_complete;
      const source = new Blob([JSON.stringify(data)], {type:'application/json'});
      const blob = await new Response(source.stream().pipeThrough(new CompressionStream('gzip'))).blob();
      const url=URL.createObjectURL(blob), anchor=document.createElement('a');
      anchor.href=url;anchor.download='stoletnika-browser-export.json.gz';document.body.appendChild(anchor);anchor.click();anchor.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
      $('note').textContent='Качи изтегления файл в папката data на GitHub и стартирай Stoletnika - Temu from Chrome.';
    } catch(error) {show('Неуспешно изтегляне: ' + error.message);}
  };
  $('close').onclick = () => {if(running){stop=true;show('Изчакай текущата страница да се запази, след това затвори панела.');}else{db.close();host.remove();}};
  show(state.complete ? 'Готово: ' + state.items.length + ' продукта. Изтегли каталога.' : 'Запазени продукти: ' + state.items.length + '/' + (state.discovered_products || '?') + '. Натисни „Старт / Продължи“.');
})().catch(error => {console.error(error);alert('Stoletnika: ' + error.message);});
