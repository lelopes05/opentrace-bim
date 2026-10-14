# OpenTrace BIM — Design System

## Design System aprovado (Leandro, 13/10)
Copie esta seção inteira para `docs/DESIGN.md`. É a fonte única; ninguém inventa valor fora dela.

### Cores
**Definitivas (fixas, só em `style.py`):**

| token | escuro | claro | uso |
|---|---|---|---|
| `petrol` | `#3A7780` | `#2F6670` | fundo da ferramenta ativa na fileira |
| `petrol-edge` | `#6FB1BB` | `#245560` | filete de 1 px em volta da ferramenta ativa |
| `on-petrol` | `#FFFFFF` | `#FFFFFF` | texto e ícone sobre `petrol` |
| `orange` | `#F0A36B` | `#B35C22` | borda e ícone da opção marcada; faixa da seção aberta na paleta. Nunca sobre `petrol` |
| `focus-ring` | `#9ED0D8` | `#1F5560` | anel de foco do teclado, 2 px com 2 px de folga |

**Neutras: vêm da `QPalette` do aplicativo**, para casar com o tema do IngeTrazo. Os valores das maquetes servem só de referência e de teste.

| token | de onde vem | referência escuro / claro |
|---|---|---|
| `panel` | `QPalette.Window` | `#2A2C2F` / `#F4F5F6` |
| `panel-raised` | `QPalette.Button` | `#383C41` / `#E3E6E9` |
| `field` | `QPalette.Base` | `#1E2022` / `#FFFFFF` |
| `text` | `QPalette.WindowText` | `#E9ECEE` / `#1C1F22` |
| `text-muted` | `QPalette.PlaceholderText`; se não passar 4,5:1 contra `panel`, mistura de `text` com `panel` até passar | `#A8AFB6` / `#4B5259` |
| `text-disabled` | `QPalette.Disabled, WindowText` | `#7A8087` / `#8A9097` |
| `border` | `QPalette.Mid`; se não passar 3:1 contra `panel` e `field`, ajuste a luminosidade no mesmo tom até passar | `#80878F` / `#7A8188` |
| `panel-edge` | `text` com alfa 12% (escuro) / 8% (claro) | |
| `hover-wash` | `text` com alfa 8% / 6% | |
| `divider` | `text` com alfa 8% / 10% | decorativo, fica abaixo de 3:1 |

O tema é escuro quando a luminosidade de `QPalette.Window` é menor que a de `QPalette.WindowText`.

Os ícones reaproveitam as cores: `icon` = `text`, `icon-accent` = `orange`, `icon-on-active` = `on-petrol`, `icon-disabled` = `text-disabled`.

### Medidas
- **Espaços:** `space-1..6` = 2, 4, 6, 8, 12 e 16 px; `panel-inset` = 8 px.
- **Raios:** `radius-panel` = 8 px; `radius-control` = 4 px.
- **Bordas:** `border-width` = 1 px; `border-marked` = 2 px.
- **Ícones:** `icon-24` na fileira normal, `icon-20` na barra, `icon-16` na fileira compacta.
- **Alturas:** `tool-height` = 40 px; `tool-height-compact` = 28 px; `option-height` = 32 px; `control-height` = 28 px.
- **Sombra dos painéis flutuantes (`panel-shadow`):** sombra suave, deslocamento y = 8 px, desfoque 24 px, preto a 38% no escuro e 16% no claro. A paleta lateral não leva sombra.

### Tipografia
Uma família só: a fonte da interface do host (a `QFont` do aplicativo); não carregue fonte.

| estilo | tamanho e peso | onde |
|---|---|---|
| `brand` | 13 px, 700 | marca na fileira |
| `tool-label` | 12 px, 500 | nome da ferramenta |
| `section-title` | 12 px, 600 | título de grupo e de seção |
| `field-label` | 11 px, 500, cor `text-muted` | rótulo de campo |
| `field-value` | 12 px, 400, números tabulares | valor dentro do campo |
| `hint` | 11 px, 400, cor `text-muted` | texto de apoio, "Em desenvolvimento", unidades |

### Estados
| estado | ferramenta (fileira) | opção (barra) | campo |
|---|---|---|---|
| normal | sem fundo, `text` | sem contorno, dentro de grupo segmentado `panel-raised` | fundo `field`, borda `border` |
| hover | véu `hover-wash` | véu `hover-wash` | fundo `panel-raised` |
| ativo | fundo `petrol` + filete 1 px `petrol-edge`, `on-petrol`; sem hover | — | — |
| marcado | — | fundo `panel`, borda `orange` 2 px, ícone `icon-accent` | — |
| foco | anel `focus-ring` | anel `focus-ring` | anel `focus-ring` |
| desabilitado | `text-disabled` | `text-disabled`, sem véu | borda `divider`, `text-disabled`, sem fundo |
| somente leitura | — | — | fundo `panel-raised`, sem borda (largura do vão de corte) |

### Contraste
- **Texto:** 4,5:1 nos dois temas.
- **Ícone, borda de campo e anel de foco:** 3:1.
- **Se não passar:** ajuste a luminosidade no mesmo tom; não troque de cor.
