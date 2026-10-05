"""Build the local, self-contained bookmarklet setup page."""
import html
import pathlib
from urllib.parse import quote

root = pathlib.Path(__file__).resolve().parent.parent
script = (root / 'browser/stoletnika_export.js').read_text(encoding='utf-8')
bookmark = 'javascript:' + quote(script, safe='')
page = '''<!doctype html><html lang="bg"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stoletnika — старт</title><style>
body{font:17px/1.65 Arial,sans-serif;background:#edf3f6;color:#172536;margin:0;padding:36px 20px}main{max-width:850px;margin:auto;background:white;border-radius:16px;padding:36px;box-shadow:0 8px 35px #17304c15}h1{font-size:30px;margin:0 0 12px}h2{font-size:21px;margin-top:30px}a{color:#245a76}li{margin:12px 0}code{background:#edf3f6;padding:3px 6px;border-radius:4px;overflow-wrap:anywhere}.bookmark{display:inline-block;background:#245a76;color:white;padding:16px 24px;border-radius:9px;text-decoration:none;font-weight:bold}aside{background:#eef6fa;padding:14px 20px;border-radius:8px;margin:20px 0}small{color:#526375}textarea{width:100%;height:160px;box-sizing:border-box;font:12px monospace}button{font:inherit;padding:8px 16px;background:#245a76;color:white;border:0;border-radius:6px;cursor:pointer}
</style><main><h1>Stoletnika → Temu</h1><p>Каталогът се изтегля през твоя Chrome. GitHub попълва Excel от изтеглените данни. Не е нужно да инсталираш Python или разширение.</p>
<h2>1. Добави бутона в Chrome</h2><p>Натисни <strong>Ctrl + Shift + B</strong>, за да покажеш лентата с отметки. <strong>Издърпай бутона по-долу върху лентата</strong>, за да го запазиш като отметка.</p>
<a class="bookmark" draggable="true" href="BOOKMARK">Stoletnika → Temu</a><p><small>Бутонът се използва от лентата с отметки, когато е отворен сайтът Stoletnika.</small></p>
<h2>2. Изтегли каталога</h2><ol><li>Отвори <a href="https://stoletnika.eu/vendor/herbalkan" target="_blank" rel="noopener">Stoletnika — Хербалкан</a> в Chrome и изчакай страницата да зареди.</li><li>Натисни отметката <strong>Stoletnika → Temu</strong>. В сайта ще се появи панел.</li><li>Натисни <strong>Старт / Продължи</strong> и остави таба отворен. Сканират се само трите зададени категории и техните продукти.</li><li>При завършване натисни <strong>Изтегли каталога</strong>. Ще получиш <code>stoletnika-browser-export.json.gz</code>.</li></ol>
<aside>Напредъкът се пази в този Chrome. Ако затвориш таба, отвори отново сайта, натисни отметката и избери <strong>Старт / Продължи</strong>. За нови цени при следващо обновяване избери <strong>Ново сканиране</strong>.</aside>
<h2>3. Получи Excel от GitHub</h2><ol><li>Замени файловете на скрейпъра с всички файлове от този пакет. Провери файла <code>.github/workflows/stoletnika-temu.yml</code>.</li><li>Качи изтегления файл в папката <code>data</code> на GitHub с точното име <code>stoletnika-browser-export.json.gz</code>. Ако Chrome е добавил <code>(1)</code> към името, премахни го.</li><li>След commit избери <strong>Actions → Stoletnika - Temu from Chrome → Run workflow</strong>.</li><li>Изтегли <strong>Artifacts → stoletnika-temu-results</strong>. В него са <code>TEMU_STOLETNIKA.xlsx</code> и <code>review.csv</code>.</li></ol>
<aside>Цените са в EUR от момента на сканирането в Chrome. Преди качване в Temu провери <code>review.csv</code> за категории и задължителни полета, които липсват на сайта.</aside>
<h2>Ако отметката не може да се издърпа</h2><p>Добави обикновена отметка в Chrome, избери <strong>Edit / Редактиране</strong> и постави адреса по-долу в полето <strong>URL</strong>.</p><button id="copy">Копирай адреса на бутона</button><p id="copy-status"></p><textarea id="bookmark-url" readonly>BOOKMARK_TEXT</textarea>
<p><small>Кодът прави само заявки към публичните страници на stoletnika.eu и изтегля данните на твоя компютър. Ако сайтът откаже достъп, сканирането спира и запазва напредъка. GitHub не получава бисквитките на браузъра.</small></p>
<script>document.getElementById('copy').onclick=async()=>{const e=document.getElementById('bookmark-url');e.select();try{await navigator.clipboard.writeText(e.value);document.getElementById('copy-status').textContent='Копирано. Постави в URL на отметката.';}catch{document.getElementById('copy-status').textContent='Натисни Ctrl + C, за да копираш избрания адрес.';}};</script></main></html>'''
page = page.replace('BOOKMARK_TEXT', html.escape(bookmark)).replace('BOOKMARK', html.escape(bookmark, quote=True))
(root / 'STOLETNIKA_START.html').write_text(page, encoding='utf-8')
print('STOLETNIKA_START.html created')
