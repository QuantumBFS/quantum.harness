"""Post-process the generic report into a white bilingual two-page interface."""

import re
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString


ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "report" / "report.html"
LANGUAGE_MARKER = re.compile(r"⟦zh⟧([\s\S]*?)⟦en⟧([\s\S]*)")

PAGE_SWITCHER = r"""
<nav class="page-switcher" aria-label="Report pages">
  <span class="page-switcher-label">⟦zh⟧报告页⟦en⟧Report pages</span>
  <button type="button" data-set-page="0" class="active" aria-pressed="true">
    ⟦zh⟧第 1 页 · 精确电路⟦en⟧Page 1 · Exact circuits
  </button>
  <button type="button" data-set-page="1" aria-pressed="false">
    ⟦zh⟧第 2 页 · 随机噪声⟦en⟧Page 2 · Random noise
  </button>
</nav>
"""

EXTRA_STYLE = r"""
<style id="bilingual-research-theme">
:root{
  --bg:#f3f6fa;--panel:#ffffff;--ink:#172033;--muted:#637083;--line:#dbe2ea;
  --accent:#075985;--accent-soft:#eaf6fb;--warm:#9a4d08;--warm-soft:#fff7ed;
  --good:#08745a;--good-soft:#ecfdf5;--bad:#b4233a;--bad-soft:#fff1f2;
  --olive:#7a5d00;--olive-soft:#fffbeb;--code-bg:#f7fafc;
  --serif:"Iowan Old Style","Source Han Serif SC","Noto Serif CJK SC",Georgia,serif;
  --sans:"Inter","SF Pro Display","PingFang SC","Microsoft YaHei UI","Segoe UI",system-ui,sans-serif;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth;background:var(--bg)}
body{
  min-height:100vh;margin:0;color:var(--ink);
  background:
    radial-gradient(circle at 12% 0%,rgba(14,165,233,.08),transparent 28rem),
    linear-gradient(180deg,#f8fbfe 0%,#f3f6fa 100%);
}
body:before{display:none}
.wrap{max-width:1080px;margin:0 auto;padding:42px 28px 72px;position:relative}
.hero{
  min-height:0;padding:42px 46px 38px;margin:0;border:1px solid #d5dee9;border-radius:24px;
  background:linear-gradient(135deg,#ffffff 0%,#f5fbff 100%);
  box-shadow:0 16px 45px rgba(15,23,42,.08);overflow:hidden;position:relative;
}
.hero:before{
  content:"Q71";position:absolute;right:22px;top:10px;color:rgba(7,89,133,.055);
  font:900 104px/1 var(--sans);letter-spacing:-.07em;
}
.eyebrow{color:var(--accent);font-size:12px;letter-spacing:.14em;font-weight:800}
h1{font-family:var(--sans);font-size:clamp(34px,5vw,58px);line-height:1.06;letter-spacing:-.045em;max-width:17ch;margin:18px 0 15px;color:#0f172a}
.sub{font:700 14px/1.6 var(--sans);color:#456078;max-width:72ch}
.lede{font-size:16px;line-height:1.72;color:#4b5b70;max-width:78ch;margin:20px 0 0}
.page-switcher{
  position:sticky;top:12px;z-index:15;display:flex;align-items:center;gap:8px;
  width:max-content;max-width:100%;margin:18px auto 0;padding:6px;border:1px solid #d5dee9;
  border-radius:14px;background:rgba(255,255,255,.94);box-shadow:0 8px 24px rgba(15,23,42,.09);
  backdrop-filter:blur(14px);
}
.page-switcher-label{padding:0 9px;color:#7b8798;font:700 11px/1 var(--sans);letter-spacing:.08em;text-transform:uppercase}
.page-switcher button,.report-controls button{
  appearance:none;border:0;border-radius:9px;padding:9px 13px;background:transparent;color:#64748b;
  font:750 12px/1 var(--sans);cursor:pointer;transition:.16s ease;
}
.page-switcher button:hover,.report-controls button:hover{color:#0f172a;background:#f0f5f9}
.page-switcher button.active,.report-controls button.active{color:#fff;background:#075985;box-shadow:0 4px 12px rgba(7,89,133,.2)}
.report-page{
  scroll-margin-top:78px;margin:22px 0 0;padding:31px 34px;border:1px solid #d9e1ea;
  border-radius:22px;background:#fff;box-shadow:0 14px 40px rgba(15,23,42,.07);
}
.page-hidden{display:none!important}
section>h2{font-family:var(--sans);font-size:clamp(25px,3vw,34px);letter-spacing:-.03em;margin:0 0 7px;color:#111827}
section>.note{font-size:14px;line-height:1.66;color:var(--muted);max-width:88ch}
section h3{font-family:var(--sans);font-size:19px;border-top-color:#e2e8f0;margin-top:24px;padding-top:19px;color:#172033}
.para{font-size:14.5px;line-height:1.72;color:#46556a;max-width:88ch}
.card{background:#f8fafc;border-color:#dbe3ec;border-radius:14px;padding:16px 19px;margin:14px 0}
.card .title{font-family:var(--sans);font-size:15px;color:#172033}
.expected{background:#f0f8fb;border-color:#bfdde9;border-radius:13px;color:#284d60;padding:15px 18px}
.expected b{color:#075985}
.verdict{border-radius:14px;padding:16px 18px;align-items:center}
.verdict.good{background:var(--good-soft);border-color:#9cdec9}
.verdict.warn{background:var(--olive-soft);border-color:#ead787}
.verdict.bad{background:var(--bad-soft);border-color:#f1b8c1}
.verdict .label{font-family:var(--sans);font-size:19px;color:#065f46}
.verdict .why{color:#3f5360;line-height:1.52}
table{border:1px solid #dce3eb;border-radius:13px;background:#fff;overflow:hidden;box-shadow:none}
thead th{background:#f1f5f9;color:#253247;border-color:#dce3eb;padding:10px 11px}
tbody td{border-color:#e5eaf0;color:#425168;padding:10px 11px}
tbody tr:hover{background:#f8fafc}
td.num{color:#075985;font-weight:750;font-family:var(--mono)}
.kv{grid-template-columns:205px minmax(0,1fr);gap:8px 17px}
.kv .k{color:#64748b}.kv .v{color:#26364b;font-family:var(--mono)}
ul.flat li{font-size:14px;line-height:1.6;color:#46556a;margin:6px 0}
code{background:#f7fafc;color:#075985;border:1px solid #dbe3ec}
pre code{border:0;background:transparent;color:#075985;line-height:1.65}
.figs{grid-template-columns:1fr;width:100%;gap:18px}
.figbox{background:#fff;border-color:#dce3eb;border-radius:16px;padding:12px;box-shadow:0 8px 24px rgba(15,23,42,.06)}
.figbox img{border-radius:10px;background:#fff}
.figbox .cap{font-size:12.5px;line-height:1.56;color:#66758a;text-align:left;padding:4px 5px}
.toc,.toc-bar{display:none!important}
.footer{color:#7b8798;border-color:#dce3eb}
.report-controls{
  position:fixed;z-index:20;right:18px;top:16px;display:flex;gap:5px;padding:5px;
  border:1px solid #d5dee9;border-radius:12px;background:rgba(255,255,255,.95);
  box-shadow:0 8px 24px rgba(15,23,42,.1);backdrop-filter:blur(14px);
}
.lang-en{display:none}
.print-btn{display:none}
.lang-fade{animation:langFade .18s ease}
@keyframes langFade{from{opacity:.55}to{opacity:1}}
@media(max-width:760px){
  .wrap{padding:70px 13px 48px}.hero{padding:34px 22px 28px;border-radius:18px}.hero:before{font-size:60px}
  h1{font-size:36px}.lede{font-size:14.5px}.report-controls{left:13px;right:auto;top:12px}
  .page-switcher{position:static;width:100%;overflow-x:auto;justify-content:flex-start}.page-switcher-label{display:none}
  .page-switcher button{white-space:nowrap}.report-page{padding:23px 16px;border-radius:18px;margin-top:14px;overflow:hidden}
  .verdict{display:block}.verdict .label{display:block;margin-bottom:6px}
  .kv{grid-template-columns:1fr;gap:2px}.kv .v{margin-bottom:8px}
  table{display:block;overflow-x:auto;white-space:nowrap}.figs{width:100%;position:static;left:auto;transform:none}.figbox{padding:6px}
}
@page{size:A4 landscape;margin:9mm}
@media print{
  html,body{background:#fff!important;color:#111}
  .wrap{max-width:none;padding:0}.report-controls,.page-switcher,.toc,.toc-bar,.footer{display:none!important}
  .hero,.report-page{display:block!important;background:#fff;box-shadow:none;border:0;border-radius:0}
  .hero{padding:0 0 8px;margin:0}.hero:before{display:none}
  h1{font-size:25px;margin:6px 0}.sub{font-size:10px}.lede{font-size:10px;line-height:1.35;margin-top:6px}
  .report-page{margin:0;padding:6px 0 0}.report-page:nth-of-type(2){break-before:page;page-break-before:always}
  section>h2{font-size:21px;margin-bottom:3px}section>.note,.para,ul.flat li{font-size:9.5px;line-height:1.35}
  section h3{font-size:14px;margin-top:8px;padding-top:6px}
  .verdict,.card,.expected{padding:7px 9px;margin:6px 0}.verdict .label{font-size:14px}.verdict .why{font-size:9.5px}
  table{font-size:9px}.thead th,thead th,tbody td{padding:5px 6px}
  .kv{grid-template-columns:150px minmax(0,1fr);gap:3px 8px;font-size:9px}
  .figbox{box-shadow:none;padding:3px}.figbox img{max-height:245px;object-fit:contain}.figbox .cap{font-size:8px;line-height:1.25}
  .card .title{font-size:11px}.expected{font-size:9px}
}
</style>
"""

EXTRA_UI = r"""
<div class="report-controls" aria-label="Language and document controls">
  <button type="button" data-set-lang="zh" class="active" aria-pressed="true">中文</button>
  <button type="button" data-set-lang="en" aria-pressed="false">English</button>
  <button type="button" data-print aria-label="Print or save as PDF">PDF</button>
</div>
<script>
(function(){
  var sections=Array.prototype.slice.call(document.querySelectorAll('main section'));
  sections.forEach(function(section){section.classList.add('report-page');});
  document.body.setAttribute('data-report-pages',String(sections.length));
  function setPage(index,updateHash){
    index=Math.max(0,Math.min(index,sections.length-1));
    sections.forEach(function(section,sectionIndex){
      section.classList.toggle('page-hidden',sectionIndex!==index);
    });
    var hero=document.querySelector('.hero');
    if(hero) hero.classList.toggle('page-hidden',index!==0);
    document.querySelectorAll('[data-set-page]').forEach(function(button){
      var active=Number(button.getAttribute('data-set-page'))===index;
      button.classList.toggle('active',active);
      button.setAttribute('aria-pressed',String(active));
    });
    document.body.setAttribute('data-active-page',String(index+1));
    if(updateHash && sections[index] && history.replaceState){
      history.replaceState(null,'','#'+sections[index].id);
    }
    window.scrollTo({top:0,behavior:'smooth'});
  }
  function setLanguage(lang){
    document.querySelectorAll('.lang-zh').forEach(function(el){
      el.style.display=lang==='zh'?'':'none';
    });
    document.querySelectorAll('.lang-en').forEach(function(el){
      el.style.display=lang==='en'?'':'none';
    });
    ['alt','title','aria-label'].forEach(function(attr){
      document.querySelectorAll('[data-lang-'+attr+'-zh]').forEach(function(el){
        el.setAttribute(attr,el.getAttribute('data-lang-'+attr+'-'+lang));
      });
    });
    document.documentElement.lang=lang==='zh'?'zh-CN':'en';
    document.querySelectorAll('[data-set-lang]').forEach(function(button){
      var active=button.getAttribute('data-set-lang')===lang;
      button.classList.toggle('active',active);
      button.setAttribute('aria-pressed',String(active));
    });
    var footer=document.querySelector('.footer');
    if(footer) footer.textContent=lang==='zh'
      ?'更新于 2026-07-30。两页、单文件、无外部资源。'
      :'Updated 2026-07-30. Two pages, one file, no external resources.';
    document.querySelector('main').classList.remove('lang-fade');
    void document.querySelector('main').offsetWidth;
    document.querySelector('main').classList.add('lang-fade');
    document.title=document.documentElement.getAttribute('data-page-title-'+lang);
  }
  document.querySelectorAll('[data-set-page]').forEach(function(button){
    button.addEventListener('click',function(){
      setPage(Number(button.getAttribute('data-set-page')),true);
    });
  });
  document.querySelectorAll('[data-set-lang]').forEach(function(button){
    button.addEventListener('click',function(){setLanguage(button.getAttribute('data-set-lang'));});
  });
  document.querySelector('[data-print]').addEventListener('click',function(){window.print();});
  var hashIndex=sections.findIndex(function(section){return '#'+section.id===location.hash;});
  setPage(hashIndex>=0?hashIndex:0,false);
  setLanguage('zh');
})();
</script>
"""


def materialize_bilingual_markup(html: str) -> str:
    """Turn raw language markers into stable spans before delivery."""

    soup = BeautifulSoup(html, "html.parser")
    title = soup.title
    if title and title.string:
        match = LANGUAGE_MARKER.fullmatch(str(title.string))
        if match:
            soup.html["data-page-title-zh"] = match.group(1)
            soup.html["data-page-title-en"] = match.group(2)
            title.string.replace_with(match.group(1))

    marked_nodes = list(
        soup.find_all(string=lambda value: value and "⟦zh⟧" in value)
    )
    for node in marked_nodes:
        if node.parent and node.parent.name in {"script", "style", "title"}:
            continue
        text = str(node)
        match = LANGUAGE_MARKER.search(text)
        if not match:
            continue
        chinese = soup.new_tag("span")
        chinese["class"] = "lang-zh"
        chinese.string = match.group(1)
        english = soup.new_tag("span")
        english["class"] = "lang-en"
        english.string = match.group(2)
        prefix = text[: match.start()]
        node.replace_with(chinese)
        if prefix:
            chinese.insert_before(NavigableString(prefix))
        chinese.insert_after(english)

    for element in soup.find_all(True):
        for attribute in ("alt", "title", "aria-label"):
            value = element.get(attribute)
            if not isinstance(value, str):
                continue
            match = LANGUAGE_MARKER.fullmatch(value)
            if not match:
                continue
            element[f"data-lang-{attribute}-zh"] = match.group(1)
            element[f"data-lang-{attribute}-en"] = match.group(2)
            element[attribute] = match.group(1)

    return str(soup)


def main() -> None:
    html = REPORT.read_text(encoding="utf-8")
    if 'id="bilingual-research-theme"' in html:
        print(f"already enhanced {REPORT}")
        return
    html = html.replace("</header>", "</header>" + PAGE_SWITCHER, 1)
    html = materialize_bilingual_markup(html)
    html = html.replace("</head>", EXTRA_STYLE + "</head>")
    html = html.replace("</body>", EXTRA_UI + "</body>")
    REPORT.write_text(html, encoding="utf-8")
    print(f"enhanced {REPORT}")


if __name__ == "__main__":
    main()
