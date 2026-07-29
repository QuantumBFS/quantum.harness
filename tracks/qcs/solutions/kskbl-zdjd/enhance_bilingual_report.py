"""Post-process the generic offline report into a bilingual research interface."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "report.html"

EXTRA_STYLE = r"""
<style id="bilingual-research-theme">
:root{
  --bg:#080d19;--panel:#10182a;--ink:#eaf1ff;--muted:#91a2c2;--line:#24304a;
  --accent:#66e3ff;--accent-soft:#112d40;--warm:#ff9f72;--warm-soft:#3b281f;
  --good:#6ff0b0;--good-soft:#102f2b;--bad:#ff8291;--bad-soft:#3a1e29;
  --olive:#e7c76e;--olive-soft:#332e1d;--code-bg:#09111f;
  --serif:"Iowan Old Style","Source Han Serif SC","Noto Serif CJK SC",Georgia,serif;
  --sans:"Inter","SF Pro Display","PingFang SC","Microsoft YaHei UI","Segoe UI",system-ui,sans-serif;
}
html{scroll-behavior:smooth;background:#080d19}
body{
  background:
    radial-gradient(circle at 16% 2%,rgba(64,174,255,.17),transparent 31rem),
    radial-gradient(circle at 92% 24%,rgba(143,96,255,.15),transparent 28rem),
    linear-gradient(180deg,#080d19 0%,#0a1020 55%,#080d19 100%);
  min-height:100vh;
}
body:before{
  content:"";position:fixed;inset:0;pointer-events:none;opacity:.32;
  background-image:linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px);
  background-size:42px 42px;mask-image:linear-gradient(to bottom,#000,transparent 72%);
}
.wrap{max-width:1040px;padding:72px 46px 120px;position:relative}
.hero{
  min-height:430px;padding:76px 56px 48px;margin:0 0 26px;border:1px solid #293754;border-radius:30px;
  background:
    linear-gradient(135deg,rgba(19,34,59,.94),rgba(12,20,38,.9)),
    radial-gradient(circle at 80% 0%,rgba(102,227,255,.2),transparent 45%);
  box-shadow:0 30px 90px rgba(0,0,0,.34),inset 0 1px 0 rgba(255,255,255,.07);
  overflow:hidden;position:relative;
}
.hero:before{
  content:"CIRCUIT / 71";position:absolute;right:-18px;top:12px;color:rgba(143,214,255,.055);
  font:900 86px/1 var(--sans);letter-spacing:-.05em;white-space:nowrap;
}
.eyebrow{color:var(--accent);font-size:12px;letter-spacing:.16em}
h1{font-family:var(--sans);font-size:clamp(38px,5.8vw,68px);line-height:1.03;letter-spacing:-.045em;max-width:15ch;margin:24px 0 22px}
.sub{font:600 14px/1.5 var(--mono);color:#9eb2d4;max-width:62ch}
.lede{font-size:17px;line-height:1.75;color:#c7d5ed;max-width:68ch;margin-top:28px}
section{scroll-margin-top:30px;margin:64px 0 0;padding:30px 34px;border:1px solid rgba(53,69,101,.7);border-radius:24px;background:rgba(13,21,38,.76);box-shadow:0 16px 45px rgba(0,0,0,.17);backdrop-filter:blur(14px)}
section>h2{font-family:var(--sans);font-size:clamp(25px,3vw,36px);letter-spacing:-.03em;margin:0 0 8px}
section>.note{font-size:14px;line-height:1.7;color:var(--muted);max-width:82ch}
section h3{font-family:var(--sans);font-size:21px;border-top-color:#283550;margin-top:32px;padding-top:24px}
.para{font-size:15px;line-height:1.78;color:#cbd8ed;max-width:84ch}
.card{background:linear-gradient(145deg,rgba(20,31,53,.98),rgba(12,20,36,.98));border-color:#2a3856;border-radius:16px;padding:18px 21px;margin:16px 0}
.card .title{font-family:var(--sans);font-size:16px;color:#eef5ff}
.expected{background:linear-gradient(90deg,rgba(18,53,68,.95),rgba(19,32,55,.95));border-color:#2f6680;border-radius:15px;color:#caeaf3;padding:17px 20px}
.expected b{color:#83e7ff}
.verdict{border-radius:17px;padding:18px 20px;align-items:center}
.verdict.good{background:linear-gradient(100deg,#113530,#12253a);border-color:#236f63}
.verdict.warn{background:linear-gradient(100deg,#332e1d,#202536);border-color:#665a31}
.verdict .label{font-family:var(--sans);font-size:20px}
.verdict .why{color:#d2def1;line-height:1.55}
table{border-color:#283550;border-radius:15px;background:#0e1728;overflow:hidden;box-shadow:0 8px 25px rgba(0,0,0,.13)}
thead th{background:#17223a;color:#dbe8ff;border-color:#2b3958;padding:12px 13px}
tbody td{border-color:#202d46;color:#c6d4eb;padding:12px 13px}
tbody tr:hover{background:#14213a}
td.num{color:#9ceeff;font-weight:700;font-family:var(--mono)}
.kv{grid-template-columns:190px minmax(0,1fr);gap:9px 18px}.kv .k{color:#8da0c0}.kv .v{color:#d5e2f5;font-family:var(--mono)}
ul.flat li{font-size:14.5px;line-height:1.65;color:#c9d6eb;margin:7px 0}
code{background:#09111f;color:#a9efff;border:1px solid #22334f}
pre code{border:0;background:transparent;color:#b8f3ff;line-height:1.7}
.figs{grid-template-columns:1fr;width:min(1120px,94vw);gap:22px}
.figbox{background:#0d1425;border-color:#283550;border-radius:21px;padding:15px;box-shadow:0 22px 50px rgba(0,0,0,.26)}
.figbox img{border-radius:13px}.figbox .cap{font-size:13px;line-height:1.6;color:#92a4c4;text-align:left;padding:4px 6px}
.toc{width:172px;left:calc(50% - 710px);top:110px}.toc .lbl{color:#7184a7}.toc a{border-left-color:#283550;color:#8295b7;padding:6px 0 6px 14px}.toc a.on{color:#75e6ff;border-left-color:#66e3ff}
.toc-bar a{background:#111b2f;border-color:#2a3855;color:#9baac4}.toc-bar a.on{color:#79e8ff;border-color:#397894;background:#122c3d}
.footer{color:#7285a7;border-color:#25314b}
.report-controls{position:fixed;z-index:20;right:20px;top:18px;display:flex;gap:8px;padding:6px;border:1px solid #31405e;border-radius:14px;background:rgba(10,17,31,.86);box-shadow:0 12px 35px rgba(0,0,0,.3);backdrop-filter:blur(18px)}
.report-controls button{appearance:none;border:0;border-radius:9px;padding:8px 12px;background:transparent;color:#92a4c2;font:700 12px/1 var(--sans);cursor:pointer;transition:.18s ease}
.report-controls button:hover{color:#eaf3ff;background:#17243b}
.report-controls button.active{color:#07111e;background:linear-gradient(135deg,#70e6ff,#a69aff);box-shadow:0 4px 16px rgba(101,222,255,.25)}
.print-btn{display:none}
.lang-fade{animation:langFade .22s ease}
@keyframes langFade{from{opacity:.35;transform:translateY(3px)}to{opacity:1;transform:none}}
@media(max-width:720px){
  .wrap{padding:76px 15px 70px}.hero{min-height:0;padding:54px 24px 34px;border-radius:22px}.hero:before{font-size:44px}
  h1{font-size:38px}.lede{font-size:15px}.report-controls{left:15px;right:auto;top:14px}
  section{padding:24px 18px;border-radius:20px;margin-top:34px;overflow:hidden}
  .verdict{display:block}.verdict .label{display:block;margin-bottom:6px}.kv{grid-template-columns:1fr;gap:2px}.kv .v{margin-bottom:9px}
  table{display:block;overflow-x:auto;white-space:nowrap}.figs{width:100%;position:static;left:auto;transform:none}.figbox{padding:8px}
}
@media print{
  :root{--bg:#fff;--panel:#fff;--ink:#111;--muted:#555;--line:#ddd}
  body{background:#fff;color:#111}.report-controls{display:none}.hero,section{background:#fff;color:#111;box-shadow:none;border-color:#ddd}
  .hero{min-height:0;padding:20px}.hero:before{display:none}.lede,.para,section>.note,ul.flat li,.verdict .why{color:#222}
  section{break-before:auto;padding:18px}.figbox{background:#fff}.card{background:#fff;border-color:#ddd}
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
  var marker=/⟦zh⟧([\s\S]*?)⟦en⟧([\s\S]*)/;
  var entries=[];
  var titleElement=document.querySelector('title');
  var titleMatch=titleElement?titleElement.textContent.match(marker):null;
  var pageTitles=titleMatch?{zh:titleMatch[1],en:titleMatch[2]}:null;
  var walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
  var node;
  while((node=walker.nextNode())){
    var match=node.nodeValue.match(marker);
    if(match) entries.push({node:node,zh:match[1],en:match[2]});
  }
  document.querySelectorAll('[alt],[title],[aria-label]').forEach(function(el){
    ['alt','title','aria-label'].forEach(function(attr){
      if(!el.hasAttribute(attr)) return;
      var value=el.getAttribute(attr),match=value.match(marker);
      if(match) entries.push({element:el,attr:attr,zh:match[1],en:match[2]});
    });
  });
  function setLanguage(lang){
    entries.forEach(function(entry){
      var value=lang==='zh'?entry.zh:entry.en;
      if(entry.node) entry.node.nodeValue=value;
      else entry.element.setAttribute(entry.attr,value);
    });
    document.documentElement.lang=lang==='zh'?'zh-CN':'en';
    document.querySelectorAll('[data-set-lang]').forEach(function(button){
      var active=button.getAttribute('data-set-lang')===lang;
      button.classList.toggle('active',active);
      button.setAttribute('aria-pressed',String(active));
    });
    var tocLabel=document.querySelector('.toc .lbl');
    if(tocLabel) tocLabel.textContent=lang==='zh'?'目录':'Contents';
    var footer=document.querySelector('.footer');
    if(footer) footer.textContent=lang==='zh'
      ?'生成于 2026-07-28。单文件、无外部资源，可离线打开。'
      :'Generated 2026-07-28. Single file, no external assets, opens offline.';
    document.querySelector('main').classList.remove('lang-fade');
    void document.querySelector('main').offsetWidth;
    document.querySelector('main').classList.add('lang-fade');
    if(pageTitles) document.title=lang==='zh'?pageTitles.zh:pageTitles.en;
  }
  document.querySelectorAll('[data-set-lang]').forEach(function(button){
    button.addEventListener('click',function(){setLanguage(button.getAttribute('data-set-lang'));});
  });
  document.querySelector('[data-print]').addEventListener('click',function(){window.print();});
  setLanguage('zh');
})();
</script>
"""


def main() -> None:
    html = REPORT.read_text(encoding="utf-8")
    if 'id="bilingual-research-theme"' in html:
        print(f"already enhanced {REPORT}")
        return
    html = html.replace("</head>", EXTRA_STYLE + "</head>")
    html = html.replace("</body>", EXTRA_UI + "</body>")
    REPORT.write_text(html, encoding="utf-8")
    print(f"enhanced {REPORT}")


if __name__ == "__main__":
    main()
