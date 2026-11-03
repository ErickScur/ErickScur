#!/usr/bin/env python3
"""Gera os SVGs do README do perfil, sem dependência de fonte no navegador.

SVG dentro de <img> não carrega fonte externa, então todo texto vira path.
  python3 scripts/gerar.py                    tudo
  python3 scripts/gerar.py --pulso            só o gráfico de contribuições (o que a Action roda)
  python3 scripts/gerar.py --portfolio DIR    grava também o banner do repo do portfólio em DIR
Falha com exit 1 se faltar glifo, se um texto estourar a largura ou se o calendário vier incompleto.
"""
import argparse, base64, datetime as dt, math, re, sys, urllib.request
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

RAIZ = Path(__file__).resolve().parent.parent
OUT = RAIZ / "assets"
FONTES = Path(__file__).resolve().parent / "fonts"
USUARIO = "ErickScur"

PAPER, INK, INK2 = "#F3EFE7", "#121110", "#45423A"
NIGHT, NIGHT2, NIGHT3 = "#0F0E0C", "#1B1A16", "#2A2823"
ON, ON2, ON3 = "#F2EEE6", "#BDB8AC", "#8E897D"
ENG, CONT, SH, SHB = "#FF5A36", "#FFC21A", "#3552EC", "#8EA4FF"

# Mesmos valores dos marcadores DADO do portfólio.
D = dict(ig="106", tt="18,6 mil", leads="14 mil", vendas="R$ 40 mil+", ebook="163",
         mcp="120", mvp="2", modulos="13+")


class Fonte:
    cache = {}

    def __new__(cls, arq, wght, wdth=100):
        k = (arq, wght, wdth)
        if k not in cls.cache:
            o = super().__new__(cls)
            t = instancer.instantiateVariableFont(TTFont(FONTES / arq), {"wght": wght, "wdth": wdth})
            o.gs, o.cm, o.upm = t.getGlyphSet(), t.getBestCmap(), t["head"].unitsPerEm
            o.hmtx, o.kern = t["hmtx"], _kerning(t)
            cls.cache[k] = o
        return cls.cache[k]

    def glifo(self, c):
        if ord(c) not in self.cm:
            sys.exit(f"ERRO: glifo ausente na fonte: {c!r}")
        return self.cm[ord(c)]

    def avancos(self, s):
        g = [self.glifo(c) for c in s]
        out, x = [], 0
        for i, n in enumerate(g):
            out.append(x)
            x += self.hmtx[n][0]
            if i + 1 < len(g):
                x += self.kern(n, g[i + 1])
        return out, x, g

    def largura(self, s, size):
        return self.avancos(s)[1] * size / self.upm

    def d(self, s, x, y, size):
        pos, _, g = self.avancos(s)
        k = size / self.upm
        pen = SVGPathPen(self.gs, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
        for n, p in zip(g, pos):
            self.gs[n].draw(TransformPen(pen, (k, 0, 0, -k, x + p * k, y)))
        return pen.getCommands()


def _kerning(t):
    """Pares de kerning do GPOS (só PairPos, o que estas fontes usam)."""
    if "GPOS" not in t:
        return lambda a, b: 0
    g = t["GPOS"].table
    idx = {i for fr in g.FeatureList.FeatureRecord if fr.FeatureTag == "kern" for i in fr.Feature.LookupListIndex}
    subs = []
    for i in sorted(idx):
        for s in g.LookupList.Lookup[i].SubTable:
            s = getattr(s, "ExtSubTable", s)
            if s.LookupType == 2:
                subs.append(s)

    def valor(a, b):
        for s in subs:
            if a not in s.Coverage.glyphs:
                continue
            if s.Format == 1:
                for r in s.PairSet[s.Coverage.glyphs.index(a)].PairValueRecord:
                    if r.SecondGlyph == b:
                        return getattr(r.Value1, "XAdvance", 0) if r.Value1 else 0
            else:
                c1 = s.ClassDef1.classDefs.get(a, 0)
                c2 = s.ClassDef2.classDefs.get(b, 0)
                v = s.Class1Record[c1].Class2Record[c2].Value1
                if v and getattr(v, "XAdvance", 0):
                    return v.XAdvance
        return 0

    return valor


ARC = "archivo-var-5.3.0.woff2"
MONO = "martian-mono-var-5.3.0.woff2"
DISPLAY = Fonte(ARC, 800, 125)
FORTE = Fonte(ARC, 700, 112)
TEXTO = Fonte(ARC, 500, 100)
MN = Fonte(MONO, 400, 87)
MNB = Fonte(MONO, 600, 87)


def t(s, x, y, size, f=TEXTO, fill=INK, anchor="start", cls=None, maxw=None):
    w = f.largura(s, size)
    if maxw and w > maxw:
        sys.exit(f"ERRO: texto estoura {maxw}px ({w:.0f}px): {s!r}")
    if anchor == "end":
        x -= w
    elif anchor == "middle":
        x -= w / 2
    c = f' class="{cls}"' if cls else ""
    return f'<path{c} fill="{fill}" d="{f.d(s, x, y, size)}"/>'


def linhas(s, f, size, maxw):
    out, atual = [], ""
    for p in s.split():
        n = f"{atual} {p}".strip()
        if f.largura(n, size) > maxw and atual:
            out.append(atual)
            atual = p
        else:
            atual = n
    return out + [atual]


def seta(x, y, s, cor, w=2.4):
    return (f'<path d="M{x} {y+s}L{x+s} {y}M{x+s*.28:.1f} {y}H{x+s}V{y+s*.72:.1f}" fill="none" '
            f'stroke="{cor}" stroke-width="{w}" stroke-linecap="square"/>')


def surge(c, entra, total, dy=7, sai=None):
    """Elemento que entra em `entra`s e some perto do fim, num ciclo de `total`s."""
    sai = total - 0.5 if sai is None else sai
    p = lambda v: f"{v / total * 100:.2f}%"
    return (f".{c}{{animation:{c} {total}s ease infinite}}"
            f"@keyframes {c}{{0%,{p(entra)}{{opacity:0;transform:translateY({dy}px)}}"
            f"{p(entra + .35)},{p(sai)}{{opacity:1;transform:none}}{p(sai + .3)},100%{{opacity:0;transform:none}}}}")


def svg(w, h, corpo, css="", titulo="", r=22, fundo=NIGHT):
    base = "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-label="{titulo}"><title>{titulo}</title><style>{css}{base}</style>'
            f'<defs><clipPath id="borda"><rect width="{w}" height="{h}" rx="{r}"/></clipPath></defs>'
            f'<g clip-path="url(#borda)"><rect width="{w}" height="{h}" fill="{fundo}"/>{corpo}</g></svg>')


def salvar(nome, conteudo, destino=OUT):
    destino.mkdir(parents=True, exist_ok=True)
    (destino / nome).write_text(conteudo, encoding="utf-8")
    print(f"{nome}: {len(conteudo) / 1024:.0f} KB")


# ---------------------------------------------------------------- hero
def foto(x, y, h):
    b = base64.b64encode((Path(__file__).parent / "erick-scur-recorte.webp").read_bytes()).decode()
    return f'<image x="{x}" y="{y}" width="{h * 591 / 1000:.0f}" height="{h}" href="data:image/webp;base64,{b}"/>'


def camadas(cx, topo, base):
    """As três cores do site, empilhadas atrás da foto."""
    x, w = cx - 170, 340
    bloco = lambda cor, a: f'<rect x="{x}" y="{topo}" width="{w}" height="{base - topo + 40}" rx="26" fill="{cor}"/>'
    return (f'<g class="cA"><g class="fA">{bloco(SH, 0)}</g></g><g class="cB"><g class="fB">{bloco(CONT, 0)}</g></g>'
            f'<g class="cC">{bloco(ENG, 0)}</g>')


CSS_CAMADAS = (
    ".cA,.cB,.cC,.fA,.fB{transform-box:fill-box;transform-origin:50% 100%}"
    ".cA{transform:rotate(5deg);animation:ca 1.1s cubic-bezier(.2,.8,.2,1) .35s both}"
    ".cB{transform:rotate(-3.5deg);animation:cb 1.1s cubic-bezier(.2,.8,.2,1) .25s both}"
    ".cC{animation:cc 1.1s cubic-bezier(.2,.8,.2,1) .15s both}"
    "@keyframes ca{from{transform:translateY(120%) rotate(0)}}@keyframes cb{from{transform:translateY(120%) rotate(0)}}"
    "@keyframes cc{from{transform:translateY(120%)}}"
    ".fA{animation:fa 7s ease-in-out 1.6s infinite alternate}.fB{animation:fb 9s ease-in-out 1.6s infinite alternate}"
    "@keyframes fa{to{transform:rotate(2.5deg)}}@keyframes fb{to{transform:rotate(-2deg)}}"
)


def hero():
    w, h, banda = 900, 500, 44
    pilha = ("Node.js · TypeScript · NestJS · Kafka · RabbitMQ · PostgreSQL · MongoDB · Redis · Docker · Terraform · "
             "Azure · AWS · Next.js · Prisma · Python · FastAPI · Claude Code · OpenAI · Stripe · Electron · ffmpeg · Remotion · ")
    lm = MN.largura(pilha, 14)
    css = (
        CSS_CAMADAS +
        ".l1,.l2{animation:sobe 1s cubic-bezier(.16,1,.3,1) both}.l1{animation-delay:.1s}.l2{animation-delay:.22s}"
        "@keyframes sobe{from{transform:translateY(125px)}}"
        ".ponto{transform-box:fill-box;transform-origin:center;animation:pop .6s cubic-bezier(.3,1.7,.5,1) .95s both,pulsa 2.6s ease-in-out 2s infinite}"
        "@keyframes pop{from{transform:scale(0)}}@keyframes pulsa{50%{opacity:.45}}"
        ".foto{animation:fotoin 1.2s cubic-bezier(.16,1,.3,1) .4s both}@keyframes fotoin{from{transform:translateY(70px);opacity:0}}"
        ".sub{animation:ent .8s ease .75s both}.eb{animation:ent .8s ease .05s both}@keyframes ent{from{opacity:0;transform:translateY(10px)}}"
        f".mq{{animation:mq {lm / 26:.0f}s linear infinite}}@keyframes mq{{to{{transform:translateX(-{lm:.1f}px)}}}}"
    )
    tit_h = 112
    y1, y2 = 186, 292
    fim_scur = DISPLAY.largura("Scur", tit_h) + 48
    corpo = (
        f'<g class="eb"><rect x="48" y="52" width="30" height="3" fill="{ENG}"/>'
        + t("erickscur.com.br", 90, 60, 18, MN, INK2) + "</g>"
        f'<clipPath id="c1"><rect x="40" y="86" width="520" height="112"/></clipPath>'
        f'<clipPath id="c2"><rect x="40" y="198" width="520" height="104"/></clipPath>'
        f'<g clip-path="url(#c1)"><g class="l1">{t("Erick", 48, y1, tit_h, DISPLAY)}</g></g>'
        f'<g clip-path="url(#c2)"><g class="l2">{t("Scur", 48, y2, tit_h, DISPLAY)}</g></g>'
        f'<rect class="ponto" x="{fim_scur + 8:.0f}" y="{y2 - 24}" width="24" height="24" fill="{ENG}"/>'
        '<g class="sub">'
        + t("Eu construo sistemas.", 48, 350, 29, FORTE, maxw=500)
        + t("E ensino a construir.", 48, 386, 29, FORTE, maxw=500)
        + t("Engenharia · 1% Programador · Acordi & Scur", 48, 426, 14, MN, INK2)
        + "</g>"
        + camadas(708, 74, h - banda)
        + f'<g class="foto">{foto(578, 60, 396)}</g>'
        + f'<rect y="{h - banda}" width="{w}" height="{banda}" fill="{NIGHT}"/>'
        + f'<defs><g id="pilha">{t(pilha, 0, h - 17, 14, MN, ON2)}</g></defs><g class="mq"><use href="#pilha"/><use href="#pilha" x="{lm:.1f}"/><use href="#pilha" x="{2 * lm:.1f}"/></g>'
    )
    salvar("hero.svg", svg(w, h, corpo, css, "Erick Scur. Eu construo sistemas. E ensino a construir.", fundo=PAPER))


def botao_site():
    w, h = 900, 88
    css = (".brilho{animation:br 5s ease-in-out infinite}@keyframes br{0%,55%{transform:translateX(-300px)}100%{transform:translateX(1200px)}}"
           ".vivo{transform-box:fill-box;transform-origin:center;animation:vi 1.8s ease-out infinite}@keyframes vi{from{transform:scale(1);opacity:.7}to{transform:scale(3.2);opacity:0}}"
           ".sta{animation:st 2.4s ease-in-out infinite}@keyframes st{50%{transform:translate(3px,-3px)}}")
    corpo = (
        f'<defs><linearGradient id="g"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".13"/>'
        f'<stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient></defs>'
        f'<circle class="vivo" cx="44" cy="44" r="7" fill="{ENG}"/><circle cx="44" cy="44" r="7" fill="{ENG}"/>'
        + t("erickscur.com.br", 70, 56, 36, DISPLAY, ON)
        + t("portfólio · casos · contato", 800, 49, 13, MN, ON2, "end")
        + f'<g class="sta">{seta(826, 32, 22, ENG, 4)}</g>'
        + f'<rect class="brilho" x="0" y="-20" width="220" height="130" fill="url(#g)" transform="skewX(-18)"/>'
    )
    salvar("site.svg", svg(w, h, corpo, css, "Abrir o site: erickscur.com.br", r=18))


# ---------------------------------------------------------------- frentes
def odometro(s, x, y, size, f, cor, cid, atraso=.2):
    lh, css, out = size * 1.05, "", ""
    n = 8
    for i, ch in enumerate(s):
        if not ch.isdigit():
            out += t(ch, x, y, size, f, cor)
            x += f.largura(ch, size)
            continue
        d = int(ch)
        lw = max(f.largura(str(k), size) for k in range(10))
        col = "".join(t(str((d + k - n + 1) % 10), x, y - (n - 1 - k) * lh, size, f, cor) for k in range(n))
        c = f"{cid}{i}"
        css += (f".{c}{{animation:{c} 1.9s cubic-bezier(.12,.8,.2,1) {atraso + i * .12:.2f}s both}}"
                f"@keyframes {c}{{from{{transform:translateY({(n - 1) * lh:.1f}px)}}}}")
        out += (f'<clipPath id="k{c}"><rect x="{x - 2:.1f}" y="{y - size:.1f}" width="{lw + 4:.1f}" height="{size * 1.12:.1f}"/></clipPath>'
                f'<g clip-path="url(#k{c})"><g class="{c}">{col}</g></g>')
        x += lw
    return out, css, x


def frente(nome, n, tit, publico, cor, tinta, tinta2, num, sufixo, rotulo, frase, stats):
    w, h = 290, 430
    corpo = t(n, 24, 40, 13, MNB, tinta) + t(publico, 266, 40, 11, MN, tinta2, "end", maxw=190)
    corpo += t(tit, 24, 86, 24, DISPLAY, tinta, maxw=246)
    y = 120
    for l in linhas(frase, TEXTO, 15, 242):
        corpo += t(l, 24, y, 15, TEXTO, tinta)
        y += 21
    o, css, xf = odometro(num, 24, 300, 86, DISPLAY, tinta, nome[0])
    corpo += o
    if sufixo:
        corpo += t(sufixo, xf + 6, 300, 22, FORTE, tinta)
    corpo += t(rotulo, 24, 326, 12.5, MN, tinta, maxw=246)
    corpo += f'<rect x="24" y="342" width="242" height="1" fill="{tinta}" opacity=".35"/>'
    y = 366
    for a, b in stats:
        corpo += t(a, 24, y, 13.5, FORTE, tinta) + t(b, 266, y, 11.5, MN, tinta2, "end")
        y += 24
    salvar(f"frente-{nome}.svg", svg(w, h, corpo, css, f"{tit}: {num}{sufixo} {rotulo}", fundo=cor))


def frentes():
    frente("eng", "01", "Engenharia", "CTO, tech lead, recrutador", ENG, INK, "#2A2620", D["modulos"], "", "módulos em produção",
           "Liderança técnica de e-commerce enterprise: microsserviços orientados a eventos, do desenho ao deploy.",
           [("milhões", "de usuários"), ("5+ anos", "de backend"), ("Kafka · Azure", "Terraform")])
    frente("cont", "02", "Conteúdo", "marcas e parcerias", CONT, INK, "#2A2620", D["ig"], "mil", "seguidores no Instagram",
           "1% Programador: programação e IA para quem quer trabalhar com isso de verdade.",
           [(D["tt"], "no TikTok"), (D["leads"], "leads na base"), (D["vendas"], "em vendas")])
    frente("sh", "03", "Software house", "quem precisa de produto", SH, "#F6F2EA", "#D6DCFF", D["mcp"], "", "ferramentas MCP no Juntos360",
           "Acordi & Scur: produto sob encomenda, do diagnóstico ao deploy.",
           [(f'{D["mvp"]} semanas', "até o MVP"), ("2", "produtos no ar"), ("Next.js", "Postgres · Stripe")])


# ---------------------------------------------------------------- capas animadas
def bolha(x, y, w, h, cor, r=10):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{cor}"/>'


def capa(nome, tags, titulo, descr, tela, css, cor):
    W, H = 440, 330
    y = 262
    corpo = f'<rect width="{W}" height="214" fill="{NIGHT}"/>{tela}<rect y="214" width="{W}" height="4" fill="{cor}"/>'
    corpo += t(titulo, 22, 250, 21, DISPLAY, ON) + t(tags, 418, 248, 10.5, MN, ON3, "end", maxw=210)
    d = linhas(descr, TEXTO, 13, 396)
    if len(d) > 3:
        sys.exit(f"ERRO: descrição longa demais em {nome}")
    for l in d:
        y += 0
        corpo += t(l, 22, y + 8, 13, TEXTO, ON2)
        y += 18
    salvar(f"caso-{nome}.svg", svg(W, H, corpo, css, f"{titulo}: {descr}", r=18, fundo=NIGHT2))


def caso_nerso():
    T = 11
    css = surge("a", .4, T) + surge("b", 1.5, T, sai=3.2) + surge("c", 3.2, T) + surge("e", 5.6, T) + surge("f", 6.4, T)
    css += (f".sim{{animation:sim {T}s linear infinite}}@keyframes sim{{0%,{4.7 / T * 100:.1f}%{{fill:{NIGHT3}}}{4.9 / T * 100:.1f}%,100%{{fill:{ENG}}}}}"
            f".bar{{transform-box:fill-box;transform-origin:left;animation:bar {T}s ease infinite}}@keyframes bar{{0%,{6.8 / T * 100:.1f}%{{transform:scaleX(.75)}}{7.7 / T * 100:.1f}%,100%{{transform:none}}}}")
    u = "Lembra de revisar o PR amanhã às 9h"
    uw = TEXTO.largura(u, 12.5) + 24
    tela = (
        t("Nerso", 18, 26, 12, MNB, ON) + t("bot · online", 422, 26, 10, MN, ON3, "end")
        + f'<rect y="36" width="440" height="1" fill="{NIGHT3}"/>'
        + f'<g class="a">{bolha(422 - uw, 46, uw, 26, SH)}{t(u, 434 - uw, 63, 12.5, TEXTO, "#fff")}</g>'
        + f'<g class="b">{t("consultando TickTick…", 18, 92, 11, MN, ON3)}</g>'
        + f'<g class="c">{bolha(18, 80, 250, 50, NIGHT2)}{t("hook · confirmar escrita?", 30, 99, 10.5, MN, CONT)}'
        + t("Criar tarefa: Revisar o PR", 30, 118, 12, TEXTO, ON)
        + f'<rect class="sim" x="208" y="104" width="48" height="20" rx="6" fill="{ENG}"/>{t("Sim", 232, 118, 10.5, MNB, "#fff", "middle")}</g>'
        + f'<g class="e">{bolha(18, 138, 222, 26, NIGHT3)}{t("Tarefa criada para amanhã, 9h.", 30, 155, 12.5, TEXTO, ON)}</g>'
        + f'<g class="f">{t("memória · revisa PRs pela manhã", 18, 188, 10, MN, ON2)}'
        + f'<rect x="282" y="180" width="110" height="7" rx="3.5" fill="{NIGHT3}"/><rect class="bar" x="282" y="180" width="88" height="7" rx="3.5" fill="{CONT}"/>'
        + t("0,8", 422, 188, 10, MNB, CONT, "end") + "</g>"
    )
    capa("nerso", "engenharia + conteúdo", "Nerso", "Meu assistente pessoal com IA. Lembra com nível de confiança, avisa antes do prazo e pede permissão antes de mexer em qualquer coisa.", tela, css, ENG)


def caso_reels():
    T = 9
    css = (f".ph{{animation:ph {T}s linear infinite}}@keyframes ph{{from{{transform:translateX(0)}}to{{transform:translateX(352px)}}}}"
           + surge("w1", 2.4, T, 4) + surge("w2", 3, T, 4) + surge("w3", 3.5, T, 4) + surge("w4", 4, T, 4)
           + f".mk{{animation:mk {T}s ease infinite}}@keyframes mk{{0%,20%{{fill-opacity:.15}}26%,100%{{fill-opacity:.42}}}}")
    x0 = 66
    faixa = lambda y, cor, trechos, rot: t(rot, 18, y + 13, 10, MN, ON3) + "".join(
        f'<rect x="{x0 + a}" y="{y}" width="{b}" height="18" rx="4" fill="{cor}" fill-opacity="{o}"/>' for a, b, o in trechos)
    tela = (
        t("roteiro-042.md", 18, 26, 10.5, MN, ON3) + t("cena 3 / 8", 422, 26, 10.5, MN, ON3, "end")
        + t("## Cena 3 · /clear", 18, 50, 11.5, MNB, CONT)
        + t("Quando a conversa pesa, eu rodo /clear", 18, 70, 11.5, MN, ON)
        + f'<rect class="mk" x="16" y="78" width="330" height="20" rx="4" fill="{ENG}" fill-opacity=".42"/>'
        + t('<!-- edit: modelo=split zoom=tela@"limpa" x1.2 -->', 22, 92, 9.5, MN, ON, maxw=322)
        + faixa(112, SHB, [(0, 110, .75), (114, 88, .45), (206, 146, .75)], "V1")
        + faixa(134, ENG, [(0, 200, .8), (204, 148, .8)], "V2")
        + faixa(156, CONT, [(0, 352, .55)], "A1")
        + f'<g class="ph"><rect x="{x0}" y="106" width="2" height="74" fill="{ON}"/></g>'
        + f'<g class="w1">{t("a", 130, 203, 13, FORTE, ON)}</g>' + f'<g class="w2">{t("janela", 146, 203, 13, FORTE, CONT)}</g>'
        + f'<g class="w3">{t("fica", 202, 203, 13, FORTE, ON)}</g>' + f'<g class="w4">{t("limpa", 234, 203, 13, FORTE, ON)}</g>'
    )
    capa("reels", "conteúdo + engenharia", "Reels Pipeline", "Os Reels do canal saem editados a partir do próprio roteiro. Uma marcação no texto vira split screen, legenda, zoom e logo.", tela, css, CONT)


def troca(c1, c2, tin, T):
    p = tin / T * 100
    return (f".{c1}{{animation:{c1} {T}s linear infinite}}@keyframes {c1}{{0%,{p:.1f}%{{opacity:1}}{p + 2:.1f}%,100%{{opacity:0}}}}"
            f".{c2}{{animation:{c2} {T}s linear infinite}}@keyframes {c2}{{0%,{p:.1f}%{{opacity:0}}{p + 2:.1f}%,100%{{opacity:1}}}}")


def caso_juntos():
    T = 10
    css = (surge("a", .4, T) + surge("b", 1.4, T) + surge("e", 5.4, T) + troca("p1", "p2", 4.7, T) + troca("s1", "s2", 4.2, T) + troca("v1", "v2", 5.2, T)
           + f".cf{{animation:cf {T}s linear infinite}}@keyframes cf{{0%,{3.8 / T * 100:.1f}%{{fill:{NIGHT3}}}{4 / T * 100:.1f}%,100%{{fill:{SH}}}}}")
    tela = (
        t("Juntos360", 18, 26, 12, MNB, ON) + t("cliente A.M.", 18, 42, 10, MN, ON3)
        + f'<rect x="186" y="0" width="1" height="214" fill="{NIGHT3}"/>'
        + t("patrimônio", 18, 58, 10, MN, ON3)
        + f'<g class="v1">{t("R$ 184.300", 18, 84, 21, DISPLAY, ON)}</g><g class="v2">{t("R$ 186.800", 18, 84, 21, DISPLAY, ON)}{t("+ R$ 2.500 hoje", 18, 104, 10.5, MN, CONT)}</g>'
        + t("saúde financeira", 18, 138, 10, MN, ON3) + t("74", 18, 170, 26, DISPLAY, SHB) + t("saudável", 62, 170, 11, MN, ON2)
        + t("exemplo, sem dado real", 18, 198, 9.5, MN, ON3)
        + t("Assistente via MCP", 200, 26, 11, MNB, ON) + t(f'{D["mcp"]} tools', 424, 26, 10, MN, ON3, "end")
    )
    pedido = linhas("Registrar aporte de R$ 2.500 para a cliente A.M.", TEXTO, 11.5, 204)
    tela += f'<g class="a">{bolha(200, 38, 224, 44, SH)}' + "".join(t(l, 210, 56 + i * 16, 11.5, TEXTO, "#fff") for i, l in enumerate(pedido)) + "</g>"
    tela += (f'<g class="b">{bolha(200, 90, 224, 78, NIGHT2)}{t("registrar_aporte", 210, 108, 10.5, MNB, ON)}'
             f'<g class="s1">{t("pendente", 414, 108, 9.5, MN, CONT, "end")}</g><g class="s2">{t("executada", 414, 108, 9.5, MN, SHB, "end")}</g>'
             + t("valor: 2.500,00", 210, 126, 10, MN, ON2)
             + f'<rect class="cf" x="210" y="136" width="90" height="23" rx="6" fill="{SH}"/>{t("Confirmar", 255, 152, 10.5, MNB, "#fff", "middle")}</g>'
             + f'<g class="e">{t("Aporte registrado · auditado", 200, 192, 11, TEXTO, ON)}</g>')
    capa("juntos", "software house + engenharia", "Juntos360", f'Gestão financeira e CRM para consultores de investimento. São {D["mcp"]} ferramentas para operar tudo conversando com uma IA, e cada escrita é confirmada.', tela, css, SH)


def caso_candidatus():
    T = 10
    est = ["filtros", "similaridade", "soma", "diversifica", "explica"]
    css, tela, x = "", t("Candidatus", 18, 26, 12, MNB, ON) + t("recomendação em 5 estágios", 422, 26, 10, MN, ON3, "end"), 18
    larg = 77
    for i, e in enumerate(est):
        tin = .4 + i * .9
        c = f"st{i}"
        css += f".{c}{{animation:{c} {T}s linear infinite}}@keyframes {c}{{0%,{tin / T * 100:.1f}%{{fill:{NIGHT3}}}{(tin + .2) / T * 100:.1f}%,100%{{fill:{SH}}}}}"
        tela += f'<rect class="{c}" x="{x}" y="40" width="{larg}" height="24" rx="6" fill="{SH}"/>' + t(e, x + larg / 2, 56, 9.5, MN, ON, "middle", maxw=larg - 2)
        x += larg + 4
    linhas_v = [("A", "Dev Jr. Backend", "Empresa A · remoto", "92%", True), ("E", "Dev Pleno", "3+ anos", "", False), ("C", "Dev Front-end Jr.", "Empresa C · híbrido", "86%", True),
                ("D", "Estágio QA", "Empresa D · remoto", "81%", True)]
    y, novos = 74, {"A": 0, "C": 1, "D": 2}
    for i, (l, a, b, pct, fica) in enumerate(linhas_v):
        c = f"ln{i}"
        final = 74 + novos.get(l, i) * 34
        if fica:
            css += (f".{c}{{animation:{c} {T}s cubic-bezier(.3,.9,.3,1) infinite}}"
                    f"@keyframes {c}{{0%,20%{{transform:translateY({y - final}px)}}32%,100%{{transform:none}}}}")
        else:
            css += f".{c}{{animation:{c} {T}s linear infinite}}@keyframes {c}{{0%,12%{{opacity:1}}20%,100%{{opacity:0}}}}"
        yy = final
        g = bolha(18, yy, 404, 30, NIGHT2, 7) + t(a, 30, yy + 19, 12, FORTE, ON) + t(b, 170, yy + 19, 10, MN, ON3)
        if pct:
            pc = f"pc{i}"
            css += surge(pc, 5 + i * .5, T, 2)
            g += f'<g class="{pc}">{t(pct, 410, yy + 20, 14, DISPLAY, CONT, "end")}</g>'
        tela += f'<g class="{c}">{g}</g>'
        y += 34
    capa("candidatus", "software house + engenharia", "Candidatus", "Copiloto de carreira para o primeiro emprego em tecnologia. Recomendação de vagas apoiada em pesquisa publicada. É o nosso TCC.", tela, css, SH)


def caso_maquina():
    T = 9
    nos = [("reel", "cliques", "3.871", "3.872"), ("guia", "downloads", "9.540", "9.541"), ("crm", "leads", "14.207", "14.208"),
           ("checkout", "vendas", "412", "413"), ("nfs-e", "emitida", "000412", "000413"), ("acesso", "alunos", "412", "413")]
    css = f".dot{{animation:dot {T}s cubic-bezier(.5,0,.5,1) infinite}}@keyframes dot{{"
    x0, dx = 50, 68
    for i in range(6):
        a = i * 13 + 3
        css += f"{a}%,{a + 8}%{{transform:translateX({i * dx}px)}}"
    css += f"90%{{transform:translateX({5 * dx}px);opacity:1}}95%,100%{{transform:translateX({5 * dx}px);opacity:0}}}}"
    tela = (t("do Reel à nota fiscal", 18, 26, 11, MNB, ON) + t("números ilustrativos", 422, 26, 10, MN, ON3, "end")
            + f'<rect x="{x0}" y="82" width="{5 * dx}" height="2" fill="{NIGHT3}"/>')
    for i, (n, r, a, b) in enumerate(nos):
        x = x0 + i * dx
        tin = (i * 13 + 3) / 100 * T + .15
        css += troca(f"x{i}", f"y{i}", tin, T)
        tela += (f'<circle cx="{x}" cy="83" r="17" fill="{NIGHT2}" stroke="{NIGHT3}" stroke-width="2"/>'
                 + t(f"0{i + 1}", x, 87, 10, MNB, ON2, "middle") + t(n, x, 124, 10.5, MNB, ON, "middle")
                 + t(r, x, 142, 9, MN, ON3, "middle")
                 + f'<g class="x{i}">{t(a, x, 164, 11, FORTE, ON2, "middle")}</g><g class="y{i}">{t(b, x, 164, 11, FORTE, CONT, "middle")}</g>')
    tela += f'<g class="dot"><circle cx="{x0}" cy="83" r="6" fill="{CONT}"/></g>' + t("nada depende de alguém lembrar", 220, 198, 11, MN, ON2, "middle")
    capa("maquina", "conteúdo + engenharia", "A máquina do 1%", "Do Reel ao lead, do lead à venda, da venda à nota fiscal. Guias, CRM e automações para o negócio não depender de planilha.", tela, css, CONT)


def caso_todos():
    W, H = 440, 330
    css = ".sta{animation:st 2.4s ease-in-out infinite}@keyframes st{50%{transform:translate(6px,-6px)}}"
    corpo = (t("estudos de caso", 26, 44, 13, MN, INK) + t("O problema,", 26, 130, 37, DISPLAY) + t("o que eu decidi,", 26, 174, 37, DISPLAY, maxw=390)
             + t("o que mudou.", 26, 218, 37, DISPLAY) + t("Todos no site. Os privados aparecem só como arquitetura.", 26, 256, 12.5, TEXTO, INK, maxw=390)
             + f'<g class="sta">{seta(372, 274, 34, INK, 6)}</g>')
    salvar("caso-todos.svg", svg(W, H, corpo, css, "Ler todos os estudos de caso no site", r=18, fundo=CONT))


# ---------------------------------------------------------------- pulso: contribuições reais
def calendario():
    req = urllib.request.Request(f"https://github.com/users/{USUARIO}/contributions", headers={"User-Agent": "readme-generator"})
    s = urllib.request.urlopen(req, timeout=30).read().decode()
    datas = dict(re.findall(r'data-date="(\d{4}-\d\d-\d\d)" id="(contribution-day-component-\d+-\d+)"', s))
    ids = {v: k for k, v in datas.items()}
    dias = {}
    for alvo, txt in re.findall(r'<tool-tip[^>]*for="(contribution-day-component-\d+-\d+)"[^>]*>([^<]*)</tool-tip>', s):
        m = re.match(r"([\d,]+) contribution", txt)
        if alvo in ids:
            dias[ids[alvo]] = int(m.group(1).replace(",", "")) if m else 0
    if len(dias) < 300:
        sys.exit(f"ERRO: calendário incompleto ({len(dias)} dias). O HTML do GitHub mudou?")
    return dict(sorted(dias.items()))


def pulso():
    dias = calendario()
    datas = list(dias)
    total = sum(dias.values())
    semanas = [[dias[d] for d in datas[i:i + 7]] for i in range(0, len(datas), 7)]
    semanas = [s + [0] * (7 - len(s)) for s in semanas]
    n = len(semanas)
    W, H = 900, 560
    x0, x1, topo, passo = 110, 860, 150, 7.1
    res = 112

    def alt(sem, i):
        """Interpola os 7 dias da semana e mistura com as semanas vizinhas, para virar relevo."""
        u = (i / (res - 1)) * 6
        soma = 0.0
        for j, peso in ((-1, .1), (0, 1), (1, .1)):
            if not 0 <= sem + j < n:
                continue
            for k, v in enumerate(semanas[sem + j]):
                soma += peso * v ** .72 * math.exp(-((u - k) ** 2) / .15)
        env = math.sin(math.pi * i / (res - 1)) ** .6
        return soma * env

    pico = max(alt(s, i) for s in range(n) for i in range(res))
    cores = [(53, 82, 236), (255, 194, 26), (255, 90, 54)]

    def cor(f):
        a, b, k = (cores[0], cores[1], f * 2) if f < .5 else (cores[1], cores[2], (f - .5) * 2)
        return "#%02X%02X%02X" % tuple(round(a[c] + (b[c] - a[c]) * k) for c in range(3))

    css, rid = "", ""
    for s in range(n):
        base = topo + s * passo
        pts = [(x0 + (x1 - x0) * i / (res - 1), base - alt(s, i) / pico * 128) for i in range(res)]
        d = "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
        c = cor(s / (n - 1))
        atraso = .2 + s * .045
        rid += (f'<path d="{d}" fill="{NIGHT}" stroke="{c}" stroke-width="1.35" pathLength="1" class="r" '
                f'style="animation-delay:{atraso:.2f}s,{4 + s * .09:.2f}s"/>')
    css = (".r{stroke-dasharray:1;animation:des 1.5s cubic-bezier(.3,.7,.3,1) both,onda 9s ease-in-out infinite}"
           "@keyframes des{from{stroke-dashoffset:1}}@keyframes onda{0%,12%,100%{stroke-opacity:1}5%{stroke-opacity:.25}}")
    meses = "jan fev mar abr mai jun jul ago set out nov dez".split()
    rot, visto = "", None
    for s in range(n):
        d = dt.date.fromisoformat(datas[min(s * 7, len(datas) - 1)])
        if d.month != visto:
            visto = d.month
            rot += t(meses[d.month - 1], 40, topo + s * passo + 3, 10, MN, ON3)
    tot = f"{total:,}".replace(",", ".")
    ate = dt.date.fromisoformat(datas[-1])
    corpo = (t("últimos 12 meses no GitHub · relevo das contribuições", 40, 46, 12, MN, ON3)
             + t(tot, 40, 100, 50, DISPLAY, ON) + t("contribuições", 40 + DISPLAY.largura(tot, 50) + 14, 100, 18, FORTE, ON2)
             + rid + rot
             + t(f"gerado de dados reais · atualizado em {ate.strftime('%d/%m/%Y')}", 860, 536, 10.5, MN, ON3, "end"))
    salvar("pulso.svg", svg(W, H, corpo, css, f"{tot} contribuições nos últimos 12 meses, desenhadas como relevo"))


# ---------------------------------------------------------------- carreira
def carreira():
    W, H = 900, 400
    ax0, ax1, ano0, ano1 = 134, 868, 2018, 2027
    X = lambda a: ax0 + (a - ano0) / (ano1 - ano0) * (ax1 - ax0)
    pistas = [("engenharia", ENG, 130), ("conteúdo", CONT, 204), ("software house", SHB, 278), ("formação", ON2, 348)]
    y = {p[0]: p[2] for p in pistas}
    cor = {p[0]: p[1] for p in pistas}
    passos = [
        ("formação", 2018.1, "Técnico, IFC", "c"), ("software house", 2020.45, "Scur T.I.", "c"), ("engenharia", 2020.85, "Whap", "c"),
        ("engenharia", 2021.3, "ADV", "b"), ("engenharia", 2022.2, "Premiersoft", "c"), ("conteúdo", 2023.05, "1% Programador", "c"),
        ("engenharia", 2023.12, "Nestlé", "c"), ("formação", 2023.55, "Eng. de Software, FAG", "c"), ("conteúdo", 2025.2, "Dev de Verdade", "c"),
        ("software house", 2025.45, "Candidatus", "c"), ("conteúdo", 2026.28, "E-book + CRM", "b"), ("engenharia", 2026.28, "Nerso", "c"),
        ("software house", 2026.45, "Juntos360", "c"), ("engenharia", 2026.55, "Staff", "b"), ("conteúdo", 2026.8, "Pipeline", "c"),
    ]
    corpo = t("De Videira à Nestlé, em 15 passos.", 32, 54, 25, DISPLAY, ON, maxw=840)
    for a in range(ano0, ano1 + 1):
        corpo += f'<rect x="{X(a):.1f}" y="82" width="1" height="290" fill="{NIGHT3}"/>' + t(str(a), X(a), 386, 10, MN, ON3, "middle")
    for nome, c, yy in pistas:
        corpo += t(nome, 32, yy + 4, 10, MN, c, maxw=94)
        corpo += f'<rect x="{ax0}" y="{yy}" width="{ax1 - ax0}" height="1" fill="{NIGHT3}"/>'
    css = (".traco{transform-box:fill-box;transform-origin:left;animation:tr 3.4s cubic-bezier(.3,.6,.2,1) .2s both}@keyframes tr{from{transform:scaleX(0)}}"
           ".pt{transform-box:fill-box;transform-origin:center;animation:ptin .5s cubic-bezier(.3,1.8,.5,1) both}@keyframes ptin{from{transform:scale(0);opacity:0}}"
           ".rt{animation:rt .5s ease both}@keyframes rt{from{opacity:0;transform:translateY(5px)}}"
           ".ao{transform-box:fill-box;transform-origin:center;animation:ao 2.4s ease-out 4s infinite}@keyframes ao{from{transform:scale(1);opacity:.6}to{transform:scale(3);opacity:0}}")
    for nome, c, yy in pistas:
        ini = min(a for n, a, *_ in passos if n == nome)
        corpo += f'<rect class="traco" x="{X(ini):.1f}" y="{yy - 1}" width="{ax1 - X(ini):.1f}" height="3" fill="{c}"/>'
    for nome, a, rotulo, lado in passos:
        x, yy, c = X(a), y[nome], cor[nome]
        atraso = .2 + (a - ano0) / (ano1 - ano0) * 3.2
        yt = yy - 13 if lado == "c" else yy + 21
        fim = x + MN.largura(rotulo, 10.5) / 2
        ancora = "end" if fim > 890 else "middle"
        corpo += f'<circle class="pt" style="animation-delay:{atraso:.2f}s" cx="{x:.1f}" cy="{yy}" r="6" fill="{c}"/>'
        corpo += f'<g class="rt" style="animation-delay:{atraso + .1:.2f}s">{t(rotulo, 888 if ancora == "end" else x, yt, 10.5, MN, ON, ancora)}</g>'
    xs = X(2026.55)
    corpo += f'<circle class="ao" cx="{xs:.1f}" cy="{y["engenharia"]}" r="6" fill="{ENG}"/>'
    salvar("carreira.svg", svg(W, H, corpo, css, "Linha do tempo da carreira, de 2018 a 2026, em quatro frentes"))


def pilula(nome, rot, cor=NIGHT, txt=ON):
    w = int(MNB.largura(rot, 14) + 62)
    corpo = t(rot, 22, 30, 14, MNB, txt) + seta(w - 32, 17, 12, ENG, 2.6)
    salvar(f"link-{nome}.svg", svg(w, 48, corpo, "", rot, r=24, fundo=cor))


# ---------------------------------------------------------------- banner do portfólio
def banner(destino):
    W, H, T = 900, 470, 15
    chrome = 44
    bx, by, bw = 170, 22, 560
    dom, loc = "erickscur.com.br", "localhost:8000"
    cw = MN.largura("m", 13.5)
    p = lambda v: f"{v / T * 100:.2f}%"
    wl, wd = cw * len(loc) + 2, cw * len(dom) + 2
    css = (
        f".capa-loc{{animation:cl {T}s infinite}}@keyframes cl{{0%,{p(3.0)}{{transform:translateX({wl:.1f}px)}}{p(3.8)},100%{{transform:none;animation-timing-function:steps(14)}}}}"
        f".capa-dom{{animation:cd {T}s infinite}}@keyframes cd{{0%,{p(4.0)}{{transform:none;animation-timing-function:steps(16)}}{p(5.4)},100%{{transform:translateX({wd:.1f}px)}}}}"
        f".site{{animation:si {T}s infinite}}@keyframes si{{0%,{p(5.5)}{{opacity:0;transform:translateY(18px)}}{p(6.1)},{p(14.3)}{{opacity:1;transform:none}}{p(14.8)},100%{{opacity:0}}}}"
        f".term{{animation:te {T}s infinite}}@keyframes te{{0%,{p(5.2)}{{opacity:1}}{p(5.6)},{p(14.8)}{{opacity:0}}100%{{opacity:1}}}}"
        f".l0{{animation:l0 {T}s linear infinite}}@keyframes l0{{0%,{p(5.3)}{{opacity:1}}{p(5.4)},100%{{opacity:0}}}}"
        f".l1b{{animation:l1b {T}s linear infinite}}@keyframes l1b{{0%,{p(5.4)}{{opacity:0}}{p(5.6)},{p(14.5)}{{opacity:1}}100%{{opacity:0}}}}"
        f".cad{{animation:cad 1s steps(2) infinite}}@keyframes cad{{50%{{opacity:0}}}}"
        + surge("tl1", .5, T, 4, 5.2) + surge("tl2", 1.3, T, 4, 5.2) + surge("tl3", 2.2, T, 4, 5.2)
    )
    x0, y0, jw, jh = 40, 26, 820, 418
    barra = NIGHT3
    janela = (
        f'<rect x="{x0}" y="{y0}" width="{jw}" height="{jh}" rx="16" fill="{PAPER}"/>'
        f'<path d="M{x0} {y0 + chrome}V{y0 + 16}a16 16 0 0 1 16-16H{x0 + jw - 16}a16 16 0 0 1 16 16V{y0 + chrome}Z" fill="{NIGHT2}"/>'
        + "".join(f'<circle cx="{x0 + 22 + i * 18}" cy="{y0 + 22}" r="5.5" fill="{c}"/>' for i, c in enumerate((ENG, CONT, SHB)))
        + f'<rect x="{x0 + bx - 40}" y="{y0 + 9}" width="{bw}" height="26" rx="13" fill="{barra}"/>'
    )
    tx, ty = x0 + bx - 20, y0 + 27
    endereco = (
        f'<clipPath id="ad"><rect x="{tx - 2}" y="{y0 + 9}" width="{bw - 30}" height="26"/></clipPath><g clip-path="url(#ad)">'
        f'<g class="l0">{t(loc, tx, ty, 13.5, MN, ON2)}<rect class="capa-loc" x="{tx - 1}" y="{y0 + 10}" width="{wl + 4:.1f}" height="24" fill="{barra}"/></g>'
        f'<g class="l1b">{t(dom, tx, ty, 13.5, MN, ON)}<rect class="capa-dom" x="{tx - 1}" y="{y0 + 10}" width="{wd + 4:.1f}" height="24" fill="{barra}"/></g></g>'
    )
    py = y0 + chrome
    terminal = (
        f'<g class="term"><path d="M{x0} {py}H{x0 + jw}V{y0 + jh - 16}a16 16 0 0 1-16 16H{x0 + 16}a16 16 0 0 1-16-16Z" fill="{NIGHT}"/>'
        f'<g class="tl1">{t("$ python3 -m http.server 8000", x0 + 34, py + 54, 15, MN, ON)}</g>'
        f'<g class="tl2">{t("Serving HTTP on 0.0.0.0 port 8000", x0 + 34, py + 84, 15, MN, ON3)}</g>'
        f'<g class="tl3">{t("Roda perfeito. E só você está vendo.", x0 + 34, py + 134, 22, FORTE, CONT)}</g></g>'
    )
    site = (
        f'<g class="site">'
        f'<clipPath id="pg"><path d="M{x0} {py}H{x0 + jw}V{y0 + jh - 16}a16 16 0 0 1-16 16H{x0 + 16}a16 16 0 0 1-16-16Z"/></clipPath><g clip-path="url(#pg)">'
        f'<rect x="{x0}" y="{py}" width="{jw}" height="{jh}" fill="{PAPER}"/>'
        + t("Erick", x0 + 40, py + 112, 92, DISPLAY) + t("Scur", x0 + 40, py + 202, 92, DISPLAY)
        + f'<rect x="{x0 + 46 + DISPLAY.largura("Scur", 92):.0f}" y="{py + 182}" width="20" height="20" fill="{ENG}"/>'
        + t("Eu construo sistemas.", x0 + 40, py + 252, 25, FORTE) + t("E ensino a construir.", x0 + 40, py + 284, 25, FORTE)
        + t("HTML, CSS e JavaScript puros.", x0 + 40, py + 326, 13, MN, INK2)
        + f'<rect x="{x0 + 460}" y="{py + 78}" width="300" height="320" rx="24" fill="{SH}" transform="rotate(-7 {x0 + 610} {py + 390})"/>'
        + f'<rect x="{x0 + 460}" y="{py + 78}" width="300" height="320" rx="24" fill="{CONT}" transform="rotate(-3.5 {x0 + 610} {py + 390})"/>'
        + f'<rect x="{x0 + 460}" y="{py + 78}" width="300" height="320" rx="24" fill="{ENG}"/>'
        + foto(x0 + 500, py + 44, 340)
        + "</g></g>"
    )
    corpo = janela + terminal + site + endereco
    salvar("banner.svg", svg(W, H - 0, corpo, css, "Do localhost para erickscur.com.br", fundo=NIGHT), destino)


def botao_portfolio(destino):
    w, h = 900, 88
    css = (".brilho{animation:br 5s ease-in-out infinite}@keyframes br{0%,55%{transform:translateX(-300px)}100%{transform:translateX(1200px)}}"
           ".vivo{transform-box:fill-box;transform-origin:center;animation:vi 1.8s ease-out infinite}@keyframes vi{from{transform:scale(1);opacity:.7}to{transform:scale(3.2);opacity:0}}"
           ".sta{animation:st 2.4s ease-in-out infinite}@keyframes st{50%{transform:translate(3px,-3px)}}")
    corpo = (
        f'<defs><linearGradient id="g"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".13"/>'
        f'<stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient></defs>'
        f'<circle class="vivo" cx="44" cy="44" r="7" fill="{ENG}"/><circle cx="44" cy="44" r="7" fill="{ENG}"/>'
        + t("erickscur.com.br", 70, 56, 36, DISPLAY, ON)
        + t("no ar · hospedado na HostGator", 806, 49, 12.5, MN, ON2, "end")
        + f'<g class="sta">{seta(826, 32, 22, ENG, 4)}</g>'
        + f'<rect class="brilho" x="0" y="-20" width="220" height="130" fill="url(#g)" transform="skewX(-18)"/>'
    )
    salvar("site.svg", svg(w, h, corpo, css, "Abrir o site: erickscur.com.br, hospedado na HostGator", r=18), destino)


def numeros(destino):
    w, h = 900, 150
    itens = [("5", "estudos de caso", ENG), ("3", "frentes, 3 cores", CONT), ("0", "framework", SHB), ("0", "etapa de build", ON)]
    corpo, css = "", ""
    lg = w / 4
    for i, (n, r, c) in enumerate(itens):
        x = i * lg + 34
        o, cs, _ = odometro(n, x, 88, 62, DISPLAY, c, "abcd"[i], .2 + i * .15)
        corpo += o + t(r, x, 118, 12.5, MN, ON2, maxw=lg - 44)
        css += cs
        if i:
            corpo += f'<rect x="{i * lg:.0f}" y="30" width="1" height="90" fill="{NIGHT3}"/>'
    salvar("numeros.svg", svg(w, h, corpo, css, "5 estudos de caso, 3 frentes, 0 framework, 0 etapa de build"), destino)


def hospedagem(destino):
    W, H, T = 900, 300, 8
    y = 190
    nos = [(120, "site.zip", "só o que é site", CONT), (345, "cPanel", "public_html", SHB), (570, "Apache", ".htaccess · HTTPS", ENG)]
    x_fim = 780
    css = (f".pac{{animation:pac {T}s cubic-bezier(.5,0,.5,1) infinite}}@keyframes pac{{0%{{transform:translateX(0);opacity:0}}4%{{opacity:1}}"
           f"30%,38%{{transform:translateX(225px)}}64%,72%{{transform:translateX(450px)}}92%{{transform:translateX(660px);opacity:1}}98%,100%{{transform:translateX(660px);opacity:0}}}}"
           f".on{{transform-box:fill-box;transform-origin:center;animation:on {T}s ease infinite}}@keyframes on{{0%,88%{{transform:scale(.97);opacity:.55}}93%,100%{{transform:none;opacity:1}}}}")
    corpo = (t("hospedagem", 40, 50, 12, MN, ON3)
             + t("No ar na HostGator.", 40, 92, 33, DISPLAY, ON)
             + t("Sem servidor de aplicação: arquivos estáticos, publicados pelo cPanel.", 40, 122, 14, TEXTO, ON2, maxw=820)
             + f'<rect x="120" y="{y - 1}" width="660" height="2" fill="{NIGHT3}"/>')
    for x, a, b, c in nos:
        corpo += (f'<circle cx="{x}" cy="{y}" r="24" fill="{NIGHT2}" stroke="{c}" stroke-width="2"/>'
                  + t(a, x, y + 52, 13, MNB, ON, "middle") + t(b, x, y + 72, 10.5, MN, ON3, "middle"))
    corpo += (f'<g class="on"><rect x="{x_fim - 16}" y="{y - 24}" width="112" height="48" rx="12" fill="{ENG}"/>'
              + t("no ar", x_fim + 40, y + 6, 15, DISPLAY, INK, "middle") + "</g>"
              + t("erickscur.com.br", x_fim + 40, y + 52, 11.5, MNB, ON, "middle", maxw=130))
    corpo += f'<g class="pac"><circle cx="120" cy="{y}" r="7" fill="{CONT}"/></g>'
    salvar("hospedagem.svg", svg(W, H, corpo, css, "Hospedado na HostGator: o zip do site vai pelo cPanel e fica no ar em erickscur.com.br"), destino)


def design(destino):
    W, H = 900, 320
    css = (".b0,.b1,.b2{animation:bl 1s cubic-bezier(.16,1,.3,1) both}.b0{animation-delay:.1s}.b1{animation-delay:.22s}.b2{animation-delay:.34s}"
           "@keyframes bl{from{transform:translateX(-430px)}}"
           ".aa{animation:aa 6s ease-in-out infinite alternate}@keyframes aa{to{transform:translateY(-8px)}}")
    faixas = [("engenharia", "--eng  #FF5A36", ENG, INK), ("conteúdo", "--cont  #FFC21A", CONT, INK), ("software house", "--sh  #3552EC", SH, "#FFFFFF")]
    corpo = ""
    for i, (n, tok, c, tx) in enumerate(faixas):
        yy = i * 106 + 2
        corpo += (f'<g class="b{i}"><rect y="{yy}" width="430" height="104" fill="{c}"/>'
                  + t(n, 34, yy + 50, 24, DISPLAY, tx, maxw=380) + t(tok, 34, yy + 76, 12, MN, tx) + "</g>")
    corpo += (t("a cor é a categoria", 470, 50, 12, MN, ON3)
              + f'<g class="aa">{t("Archivo", 470, 134, 66, DISPLAY, ON, maxw=400)}</g>'
              + t("Martian Mono, para os rótulos", 470, 176, 14, MN, ON2, maxw=400)
              + f'<rect x="470" y="200" width="396" height="1" fill="{NIGHT3}"/>'
              + t("GSAP · ScrollTrigger · SplitText · Lenis", 470, 232, 13, MN, ON, maxw=400)
              + t("View Transitions nativas", 470, 258, 13, MN, ON, maxw=400)
              + t("prefers-reduced-motion respeitado", 470, 284, 13, MN, ON, maxw=400))
    salvar("design.svg", svg(W, H, corpo, css, "Sistema de design: três cores, Archivo e Martian Mono", fundo=NIGHT), destino)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pulso", action="store_true")
    ap.add_argument("--portfolio", type=Path)
    a = ap.parse_args()
    pulso()
    if a.pulso:
        sys.exit(0)
    hero(); botao_site(); frentes(); caso_nerso(); caso_reels(); caso_juntos(); caso_candidatus(); caso_maquina(); caso_todos(); carreira()
    pilula("linkedin", "LinkedIn"); pilula("instagram", "Instagram"); pilula("tiktok", "TikTok"); pilula("email", "E-mail")
    if a.portfolio:
        banner(a.portfolio); botao_portfolio(a.portfolio); numeros(a.portfolio); hospedagem(a.portfolio); design(a.portfolio)
        for n in ("nerso", "reels", "juntos", "candidatus", "maquina", "todos"):
            salvar(f"caso-{n}.svg", (OUT / f"caso-{n}.svg").read_text(encoding="utf-8"), a.portfolio)
