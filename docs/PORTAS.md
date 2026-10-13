# OpenTrace BIM — Especificação funcional de Portas Paramétricas

**Versão:** 1.0 — decisões encerradas em 13/10/2026; errata P0 incorporada em 13/10/2026  
**Estado:** especificação de produto; **não é relatório de implementação**  
**Origem:** 27 escolhas expressas pelo responsável pelo produto em três rodadas (11 + 10 + 6), cadernos mestres de desenvolvimento e interface do OpenTrace BIM e exame somente de leitura da branch experimental.  
**Estado da cópia:** referência de implementação versionada em `docs/PORTAS.md`; a declaração original de ausência de mudanças referia-se à tarefa de especificação, anterior ao P0.

> **Regra de interpretação:** `APROVADO` significa comportamento decidido pelo responsável; `DECISÃO TÉCNICA` significa especificação complementar adotada para fechar lacunas; `EXISTENTE/EXPERIMENTAL` significa apenas presença observada no código, nunca aceitação visual no Windows; `PENDENTE` indica desenvolvimento e/ou validação por realizar. Esta versão não abre novas rodadas de perguntas.

## 1. Objetivo e princípio de produto

A ferramenta **Porta** é um componente BIM arquitetônico, não um simples sólido decorativo nem uma subtração booleana destrutiva. Deve ser rápida de inserir e editar em planta, oferecer famílias construtivas parametrizadas, atualizar o vão da parede hospedeira, respeitar representação por vista e escala, conservar identidade e histórico e exportar IFC semanticamente coerente. O padrão de interação é inspirado no Archicad, sem depender de sua biblioteca, código ou identidade visual proprietários.

A arquitetura existente é preservada: **a parede é autoridade do recorte**; o **vão** é um registro paramétrico associado a ela; a **porta** é objeto distinto com ID próprio e ligação por `opening_id`/`source_id`. Um modo adicional admite porta independente sem parede, ainda com a mesma família e propriedades.

## 2. Registro fechado das 27 decisões aprovadas

| # | Tema | Decisão aprovada |
|---|---|---|
| 01 | Método de inserção | Dois cliques: posição/face, depois orientação/dobradiça/giro |
| 02 | Face de referência | Detectada pelo cursor; inversão por `Tab` |
| 03 | Âncora padrão | Centro |
| 04 | Dimensão ao ativar | Repetir o último tamanho usado |
| 05 | Campos principais | Dimensões nominais da abertura |
| 06 | Biblioteca | Abrangente na especificação; implementação progressiva |
| 07 | Exclusão | Excluir porta e abertura vinculada, sem deixar vão livre |
| 08 | Ângulos | Representação em planta e geometria 3D independentes |
| 09 | Representação | Adaptável a vista e escala |
| 10 | Colisões | Avisar; não bloquear todo conflito automaticamente |
| 11 | Porta sem parede | Admitir porta independente |
| 12 | Vão de obra | Maior que medida nominal por folgas configuráveis |
| 13 | Cota vertical | Referência ao piso acabado |
| 14 | Profundidade do marco | Acompanhar espessura da parede, editável |
| 15 | Posição do marco | Face escolhida no primeiro clique; recuo editável |
| 16 | Guarnições | Simétricas por padrão, com opção de suprimir uma face |
| 17 | Folhas | Biblioteca paramétrica com variantes de desenho |
| 18 | Ferragens | Geometria por nível de detalhe (LOD) |
| 19 | Ângulos iniciais | Planta 90°; modelo 3D 0° (fechado) |
| 20 | Inserção independente | Submodo explícito “Porta livre” |
| 21 | Prioridade de famílias | Abrir simples; depois abrir dupla e correr |
| 22 | Folgas | Padrão por família com ajuste em cada instância |
| 23 | Correr embutida | Cavidade e adaptação reais da parede, não símbolo falso |
| 24 | Substituir modelo | Preservar localização, dimensões e propriedades compatíveis |
| 25 | Especial após prioritárias | Conjuntos compostos: bandeiras, laterais e painéis |
| 26 | Porta livre → hospedada | Associar sem reconstruir nem trocar identidade da porta |
| 27 | Materiais | Independentes para folha/faces, marco, guarnições e ferragens |

**Compatibilização das decisões 16 e 27 — decisão técnica:** guarnições partem de uma geometria simétrica e perfil comum; cada face admite material diferente. Uma face pode ser desativada sem apagar a outra. Perfis assimétricos são uma eventual expansão, não o padrão inicial.

**Compatibilização das decisões 05 e 12 — correção de 13/10:** a dimensão nominal principal é a largura/altura da **folha**, **não** a medida automática da passagem livre. `wallhole`/vão bruto é calculado com as folgas da família, conforme seção 6. O usuário pode consultar e editar as medidas correlatas sem alterar o significado do campo principal. Na interface P1, a **Largura do vão de corte** é campo derivado e somente de leitura (`wallhole_size`).

## 3. Modelo de entidades e regras invariantes

Estrutura lógica:

```text
Projeto / Pavimento / Piso acabado
          │
          ├── Parede [host_uid]
          │     └── Abertura [opening_uid]
          │             └── Porta hospedada [door_uid]
          │                  ├── Família/Tipo + parâmetros
          │                  ├── Folha(s), marcos e guarnições
          │                  ├── Ferragens e materiais
          │                  └── Símbolos dependentes da vista
          │
          └── Porta livre [door_uid] (sem host nem abertura)
                  └── Família/Tipo + posição 3D + componentes
```

Invariantes obrigatórias:

1. Uma porta hospedada vincula-se a **um vão lógico principal** na parede. Uma abertura não deve ter dois objetos de preenchimento distintos concorrendo pelo mesmo vínculo IFC.
2. Cada instância possui `id` estável (correspondente ao `door_uid` lógico), `ifc_global_id` estável e referência ao tipo; a abertura vinculada tem ID/GUID próprios.
3. A geometria e as representações 2D são projeções do mesmo modelo paramétrico, **não** cópias armazenadas como modelos concorrentes.
4. A prévia por movimento de mouse não edita a malha definitiva nem cria entradas no histórico.
5. Criar, editar, vincular, converter e excluir são transações atômicas com `Undo/Redo`.
6. Edição não substitui a identidade da instância; mudar o tipo altera componentes, não o ID da porta.
7. Um vão solto criado pela ferramenta **Abertura** continua sendo entidade válida sem porta. **Excluir a porta hospedada**, porém, elimina o vão associado conforme decisão 07.
8. O arquivo do projeto preserva todos os dados para regeneração, inclusive propriedades não imediatamente renderizadas.

**Decisão técnica:** o `kind` permanece `door`, enquanto `host_mode` identifica `hosted` ou `free`; `family_key` determina o mecanismo geométrico. Não misturar “porta livre” com “abertura livre”.

## 4. Máquina de estados de inserção

### 4.1 Porta hospedada — método padrão de dois cliques

| Estado | Cursor/preview | Ação | Resultado |
|---|---|---|---|
| `READY` | Nenhuma parede → cursor neutro e aviso contextual | Aproximar de parede elegível | Passa a `HOVER_HOST` |
| `HOVER_HOST` | Prévia do conjunto, vão e cotas temporárias; realce da parede/face e âncora central | Mover mouse | Atualiza posição e face; sem gravar |
| `HOVER_HOST` | Face ativa visível | Pressionar `Tab` | Inverte face de referência sem mover a posição longitudinal |
| `HOVER_HOST` | Preview válido | **1º clique** | Fixa posição, parede, âncora e face; passa a `ORIENT` |
| `ORIENT` | Quatro combinações da folha, decididas pelo quadrante do cursor relativamente à tangente/normal local | Mover mouse | Alterna dobradiça esquerda/direita e abertura para um lado/outro |
| `ORIENT` | Prévia de folha e arco, além de eventual interferência | **2º clique** | Valida e cria abertura + porta em UMA transação; retorna a `READY` mantendo ferramenta |
| Qualquer preview | Nada gravado | `Esc` | Cancela apenas a porta em andamento; novo `Esc` pode sair da ferramenta, segundo convenção do host |
| `ORIENT` | Valores alteráveis | Digitar largura/altura em campos rápidos | Atualiza prévia; sem quebrar a etapa do clique |

O eixo da parede é parametrizado por **distância curvilínea local**; em paredes curvas o sentido de esquerda/direita é calculado a partir da tangente local e da normal da face selecionada, não de uma direção global X/Y fixa. O uso de `Tab` para inverter a face traz risco técnico no Qt: a tecla pode alterar o foco antes de atingir a ferramenta; testar e resolver em P1. O segundo clique tem quatro orientações para folha simples, sem giro involuntário do lado do acabamento. O ponto âncora fica no centro por padrão, mas a barra oferece centro/esquerda/direita; alterar a largura mantém a âncora fixa.

**Orientação é composta por variáveis distintas:** (a) face/requadro de referência; (b) posição da dobradiça; (c) lado para o qual a folha abre. “Inverter giro” altera **apenas (c)**; “Espelhar dobradiça” altera **apenas (b)**, com aviso caso a família exija remapeamento de ferragens. Para duas folhas, a segunda etapa define lado de abertura e **folha ativa** segundo regras da família, mantendo a escolha explícita na paleta se não puder ser inferida sem ambiguidade.

**Decisões técnicas de ergonomia:** `Esc` é reversível durante a prévia; ao concluir uma porta a ferramenta permanece ativa; `Ctrl+Z` reverte uma porta completa por vez; `Shift` pode atuar como restrição angular onde suportado pelo host; o cursor deve mostrar unidade, âncora e estados de invalidez. Evitar teclas novas que conflitem com atalhos existentes do IngeTrazo.

### 4.2 Porta livre — mesmo instrumento, submodo explícito

A barra de métodos expõe `Na parede` e `Porta livre` (modo ativo indicado). Em `Porta livre`, primeiro clique determina posição XY no plano de trabalho/nivel ativo e segundo clique define orientação horizontal; elevação é dada pelo piso acabado e offset ou campo Z. **Nenhum corte nem abertura é criado.** Há manipulação posterior de rotação, translação X/Y/Z e elevação. A seleção de uma porta livre exibe o mesmo editor da família, acrescido do bloco `Posicionamento livre` e ação `Vincular a parede`.

### 4.3 Modos que não devem surgir

Não inserir automaticamente “porta livre” ao clicar no vazio; não criar porta hospedada em parede incompatível; não confirmar porta ao primeiro clique; não exigir terceira confirmação geral; não mudar de `Criar` para `Editar` apenas porque o mouse passou sobre uma porta existente.

## 5. Organização de interface — integração obrigatória ao caderno mestre

Preservar menus nativos do IngeTrazo, **painéis flutuantes sobre a vista** para a fileira de ferramentas e as opções contextuais (conforme `docs/DECISIONS.md` e a decisão de 13/10), paleta lateral ancorável com cabeçalho horizontal e paleta radial/hotspots na viewport. A marca OpenTrace BIM e o botão de ajuda **?** ficam na fileira de ferramentas. Nada de Ribbon fixo, barra empilhada ou formulários complexos na faixa superior. A barra varia automaticamente pelo estado `Ferramenta Porta`, `Porta selecionada`, `Hotspot ativo`, `Outra ferramenta` e `Sem seleção`. Alterar valor no topo atualiza imediatamente a paleta e vice-versa, mediante **um único estado paramétrico**.

### 5.1 Painel flutuante de opções — porta em criação

```text
[PORTA] | MÉTODO [Na parede] [Livre]
  FAMÍLIA [Abrir · 1 folha ▾]   LARGURA NOMINAL [0,90 m]
  ALTURA NOMINAL [2,10 m]   ÂNCORA [● centro ▾]
  [Biblioteca/Definições…]  [Recolher ↑]
```

O painel de opções flutuante deve distribuir os elementos conforme a largura disponível ou ocultar os menos prioritários em menu compacto **sem recortar valores**. A seleção da família cabe em seletor compacto, não em galeria enorme permanente. Valores ilustrativos, não imposição normativa. Prévia de dobradiça e giro surge no segundo clique, dispensando quatro botões fixos.

### 5.2 Painel flutuante de opções — porta selecionada

```text
[PORTA P03] | [Abrir · 1 folha]
[Larg. nom. 0,90] [Alt. nom. 2,10] [Âncora ● centro]
[Inverter giro] [Definições…] [Recolher]
```

Selecionar **nunca inicia inserção**. O topo edita valores existentes pelo comando de edição com histórico. “Espelhar dobradiça”, substituição de tipo e geometria especializada ficam na paleta lateral/radial; o comando rápido único `Inverter giro` é permitido.

### 5.3 Paleta lateral — grupos recolhíveis

1. **Biblioteca e favoritos:** famílias, variante, miniatura de planta + 3D, pesquisa por nome/categoria, modelos recentes, favoritos do projeto/usuário.
2. **Dimensões:** nominal, conjunto, folha, passagem livre, vão bruto, folgas, alturas, referências de cota.
3. **Posição e referência:** âncora, face, alinhamento, recuo, cota a piso acabado, posição longitudinal, parede/nivel hospedador.
4. **Abertura e folhas:** dobradiça, lado de abertura, ângulo simbólico, ângulo 3D, folha ativa, folhas passivas, encontro/fechamento.
5. **Marco/batente:** perfil, largura aparente, profundidade automática/manual, rebaixo, encaixe, materiais e compatibilidade.
6. **Guarnições/alizares:** perfil e dimensão comum, presença interna/externa, material por face.
7. **Componentes:** folha lisa/envidraçada/almofadada/frisada, frisos, vidros, bandeira, painéis fixos, soleira.
8. **Ferragens:** conjunto funcional, posição, dimensões, tipo de puxador/maçaneta, dobradiça, fechadura, nível de detalhe.
9. **Materiais:** frente/verso da folha, bordas, batente, guarnições por face, ferragens, vidro e elementos especiais.
10. **Representação:** detalhe por escala/vista, ângulo 2D, marcador, linha de giro, vistas projetada/simbólica, substituições por vista.
11. **BIM/IFC:** ID de ocorrência (P01…), tipo, classificação, fabricante, código, propriedades, acessibilidade informativa, GUID.

Grupos especializados ocultam parâmetros incompatíveis com a família ativa (ex.: dobradiça não aparece em porta de correr). A página inicial deve expor só os mais usados. As páginas ficam ancoradas no mesmo painel geral aprovado, sem abrir janela modal a cada clique.

### 5.4 Viewport, hotspots e cotas temporárias

Permanecem **seis hotspots arquitetônicos** para portas retangulares hospedadas: três superiores (largura e altura), três inferiores (largura e posição). A largura respeita a âncora. Complementam-se com grips especializados por família: eixo de pivô, distância de recolhimento, divisão de folhas, limites de bandeiras e laterais. **Giro e dobradiça são comandos lógicos**, não arestas livres da abertura.

Ao selecionar: mostrar largura nominal, altura, cota de piso, distância às duas extremidades do trecho de parede e, quando relevante, passagem livre; editar cotas temporárias deve mover ou redimensionar pelo mesmo motor. Seleção clicando na folha 3D, batente, contorno em planta ou marcador precisa resolver a mesma porta; nunca editar o vão de outra instância. Paleta radial opera por hotspot exato, com arraste repetido, entrada numérica e Undo.

### 5.5 Ícones, ajuda e estados

Ícones vetoriais distintos para `Abrir 1`, `Abrir 2`, `Correr aparente`, `Correr embutida`, `Composta`, `Livre`, `Inverter giro`. Tooltip claro com nome e ação. Modo sem motor funcional deve ser oculto ou explicitamente `Em desenvolvimento`, nunca aparentar estar operacional. Erro de geometria deve indicar motivo e opção viável; não usar apenas caixa “Erro”.

## 6. Semântica rigorosa das dimensões

Correção do responsável em 13/10: o campo principal `width`/`height` representa **as dimensões nominais da folha**, como no mercado brasileiro (“porta 80” = folha de 80 cm). O corte bruto inclui batente/conjunto e **folgas por família**, calculados separadamente. Para fechar a ambiguidade da definição da medida nominal, adotar as seguintes grandezas:

| Grandeza | Uso | Regra |
|---|---|---|
| `width`, `height` (medida nominal) | Campos principais; dimensões nominais da folha | Valor principal persistente, individual da instância |
| `unit_width`, `unit_height` | Extensão externa real do conjunto montado | Inicialmente igual à nominal, salvo ajuste específico do modelo/fabricante |
| `clearance_left/right/top/bottom` | Folgas construtivas da família com override da instância | Valores independentes e não negativos; F01: 0,04/0,04/0,04/0,00 m |
| `wallhole_width` | Largura efetivamente recortada na parede | `unit_width + clearance_left + clearance_right` |
| `wallhole_height` | Altura efetivamente recortada | `unit_height + clearance_top + clearance_bottom` quando houver folga inferior de obra |
| `leaf_width/height` | Dimensões físicas de cada folha | Derivadas do conjunto, dos marcos e das folgas móveis; permitem override validado |
| `clear_passage_width/height` | Passagem útil real quando aberta | Geometria de marco, folha e ferragem intrusiva, não cópia da nominal |
| `frame_depth` | Profundidade da peça dentro da espessura da parede | Automática pela espessura acabada ou override |
| `bottom_elevation` | Cota da soleira/folha | `finished_floor_elevation + offset` |

Para porta convencional sem soleira elevada, o limite inferior do corte termina no **piso acabado**. A folga inferior da folha ou o vão sob a porta **não** devem recortar automaticamente a laje. Quando houver soleira, desnível, vão inferior especial ou porta de correr com trilho embutido, componentes e cortes complementares precisam ser modelados explicitamente segundo a família e permissões do hospedeiro.

**Exemplo meramente explicativo:** folha nominal de 0,90 m, conjunto externo de 0,90 m e folga de instalação de 0,04 m em cada lado → vão bruto de 0,98 m. A passagem livre será **menor ou diferente**, calculada do conjunto e do ângulo efetivo; não é garantidamente 0,90 m. Esses valores não são prescrições de norma.

**Decisão técnica — cotas comerciais:** presets iniciais 0,60/0,70/0,80/0,90/1,00 m para folha simples, 1,20/1,40/1,60/1,80 m para dupla, e alturas 2,10/2,20/2,40 m, com valores livres. Presets são **opções de inicialização**, não bloqueio de medidas nem certificado de conformidade. Todas as cotas armazenadas em metros, exibidas segundo unidades e arredondamento do projeto.

**Validação:** valores físicos positivos, ausência de largura negativa de folha ou passagem, respeito aos encontros geométricos, folgas compatíveis com o modelo. Requisitos de acessibilidade só aparecem como avaliação informativa apoiada em regras configuradas, **não como declaração automática de atendimento normativo**.

## 7. Posição vertical, piso acabado, face e parede composta

Porta hospedada guarda `reference_level_id` e `finished_floor_reference` mais `offset`. Piso acabado pode ser plano de acabamento associado ao pavimento ou referência de nível equivalente; a dependência é resolvida por um adaptador de níveis. Quando a cota do piso acabado muda, a porta acompanha, preservando seu deslocamento relativo. Se a referência fica ausente, manter a última cota válida e sinalizar necessidade de reconciliação, sem teleportar o objeto.

No primeiro clique, a face sob o cursor torna-se referência para batente/requadro. Em parede multicamada, profundidade automática = **espessura efetivamente acabada**, não espessura arbitrária do núcleo estrutural, com override por instância. Ajustes de revestimentos/reforços devem atualizar o encaixe mantendo a face de referência definida; não fazer o batente saltar para a face oposta. Posição da folha e eixo de dobradiça são deslocamentos controláveis dentro/fora do plano do batente. Duas guarnições simétricas geometricamente por padrão, com presença individual e acabamento individual. Nos encontros complexos, respeitar o sólido resultante e seus requadros.

## 8. Catálogo de famílias — escopo planejado e prioridade

| Código lógico | Família | Parametrização mínima | Prioridade |
|---|---|---|---|
| F01 | Abrir · 1 folha | dobradiça, sentido, folha, marco, ângulos separados | **Primeira** |
| F02 | Abrir · 2 folhas | folhas iguais/desiguais, folha ativa/passiva, giro por folha, encontro | **Segunda** |
| F03 | Correr aparente | sentido de deslizamento, folhas, sobreposição, trilho, recolhimento externo | **Segunda** |
| F04 | Correr embutida | nicho físico, bolsão real, camadas da parede, trilho e dimensão do recolhimento | **Segunda, dependente do motor de parede** |
| F05 | Composta | bandeira superior, laterais fixas, painéis, vidros, subdivisões | **Terceira, antes da pivotante** |
| F06 | Pivotante | posição do pivô, folha, folgas e ângulo; guarda de painel | Depois da composta |
| F07 | Articulada/camarão/sanfonada | número de módulos, direção e cinemática simplificada | Posterior |
| F08 | Vaivém/giratória/especial | parâmetros dedicados conforme viabilidade | Posterior |

Todas as famílias usam **a mesma infraestrutura de identidade, unidades, favoritos, representação, material, transformações e IFC**; somente o gerador e os parâmetros especializados mudam. Não oferecer 40 miniaturas desconexas de objetos quase iguais. Família contém variantes de folha: lisa, frisada, almofadada, envidraçada, com visor, veneziana/ventilada quando aplicável.

### 8.1 Duas folhas

Largura nominal total, distribuição 50/50 inicialmente, proporção individual ajustável; folha ativa explícita e passiva; batente único e encontro central; duas rotações independentes na modelagem 3D; na planta, arcos simbólicos por folha conforme representação, com opções de abrir apenas a folha ativa. Folga no encontro não deve ser contada duas vezes.

### 8.2 Correr aparente

Uma ou mais folhas, trilho aparente/oculto, lado de recolhimento e sobreposição. Prever espaço de deslizamento adjacente sem cortar esse trecho da parede como abertura adicional; detectar colisão real com outras portas/objetos na posição aberta, apresentar aviso. `plan_angle` não se aplica; usar posição simbólica deslizante e posição 3D por `slide_ratio` (0 fechado a 1 aberto).

### 8.3 Correr embutida: nicho verdadeiro

O gerador da parede recebe dois conjuntos geométricos lógicos: **abertura de passagem** e **câmara de recolhimento**. A câmara altera as camadas internas conforme limites e perfil do conjunto (preservando pele externa quando fisicamente possível), com guias, caixa/nicho e requadros apropriados. A parede não pode ser substituída por booleanas destrutivas nem perder estabilidade de edição. Necessário validar: comprimento de parede suficiente, espessura mínima, terminadores, multicamadas, interferências com pilares/junções e recuo da parede. Se o caso não é suportado pelo motor (por exemplo, um nicho real complexo numa curva), o programa **não** deve fingir embutimento: explica a incompatibilidade e não confirma essa família naquela parede até existir suporte. Ao excluir, restaura parede e camadas, inclusive câmara.

### 8.4 Composta (prioridade antes de pivotante)

Árvore de painéis: folha(s) + bandeira opcional + lateral fixa esquerda/direita + subdivisões de vidro/painel. Dimensão geral externa, altura da bandeira, largura das laterais e área operacional da porta independentes; mudar dimensões mantém restrições de mínimos e proporções ou retorna erro justificativo. Toda a composição é uma **instância lógica selecionável** com subcomponentes editáveis na paleta. Representação 2D deve distinguir os fixos da folha operável. Na exportação IFC, evitar duplicar uma mesma geometria em `IfcDoor` e `IfcWindow` sem um contrato explícito de agrupamento; por padrão a composição é um conjunto `IfcDoor` com representação consolidada e atributos dos subcomponentes. Separar entidades IFC apenas em modo avançado quando necessário e semanticamente bem definido.

## 9. Modelagem de componentes, acabamentos e ferragens

Hierarquia da porta: **folha(s)** (face A/face B, miolo, bordas, vidro e montantes se houver), **marco/batente**, **guarnição lado A/B**, **soleira**, **ferragens** (puxador/maçaneta, fechadura, dobradiças, trilhos/pivôs, molas quando disponíveis), **componentes especiais** (bandeira, lateral fixa, painel decorativo). Cada componente tem `component_key` estável, atributos próprios e, onde fizer sentido, `material_id` independente. Material não se define apenas por um `material_name` geral.

Folhas paramétricas iniciais: lisa, frisada, almofadada, envidraçada/visor. A família escolhe variante e seus parâmetros; alterar variante não reconstrói a instância BIM. Materiais diferentes frente/verso são permitidos. Guarnições usam perfil comum dos dois lados por padrão, mas podem ter materiais distintos; é possível desligar um lado. Batente pode usar espessura e perfil próprios.

Ferragens não precisam ser modeladas como mecanismo físico completo desde o começo: `LOD baixo` → eixo/ponto ou representação omitida; `LOD médio` → maçaneta, dobradiças e trilho esquemáticos; `LOD alto` → peças paramétricas visíveis com proporções válidas. Permitir catálogos de fabricantes futuramente via interface de componentes, sem os exigir para abrir um projeto offline.

## 10. Ângulos e símbolo de abertura

Para abrir simples, campos `plan_angle = 90°` e `model_angle = 0°` **independentes por padrão**. O primeiro governa somente a representação em planta; o segundo roda a folha geométrica em 3D. Direção de giro e lado da dobradiça afetam ambos sem forçar o mesmo ângulo. Intervalo físico inicial 0° a 180° conforme família, podendo restringir a abertura real por colisões. O arco de abertura em planta utiliza o **raio real da folha e eixo da dobradiça**, não a largura bruta do corte. Para abrir dupla, guardar ângulo por folha. Em famílias de correr, substituir ângulo por estados de deslizamento específicos. O editor não exibe controles inválidos para a família.

## 11. Representação por vista, escala e LOD

A escala da vista rege espessura aparente de traços, símbolos e cotas; o zoom do monitor não altera o nível lógico da representação. Representações:

| Contexto | Conteúdo mínimo |
|---|---|
| Planta conceitual, escala pequena | Abertura simplificada, folha/arco convencionais quando pertinente, marcador Pxx opcional |
| Planta arquitetônica (ex. 1:100/1:50) | Marco, folha, giro, guarnições principais, fixos versus móveis, estilo gráfico do projeto |
| Detalhe (ex. 1:20/1:10) | Requadro, batente, perfil, folgas/soleiras, ferragens segundo LOD |
| Corte | Interseção física correta, marco e folha cortados/projetados, materiais e camadas do hospedeiro |
| Elevação | Folha, painéis, frisos, vidros, guarnições e ferragens de acordo com o LOD |
| 3D | Geometria real parametrizada, sem arcos simbólicos 2D intrusivos |
| Tabela de esquadrias | Identificação, tipo, nominais, vão bruto, folha, passagem livre, materiais e parâmetros de abertura |

Vistas podem sobrescrever nível de representação sem alterar a porta armazenada. Símbolo pode mostrar folha aberta a 90° com 3D fechado. Cortes/requadro obedecem à geometria e ao sistema de seções do IngeTrazo. Não gerar objetos duplicados no projeto para cada escala. Numeração P01, P02 etc. deve ser editável e não necessariamente igual a ID interno. Cotas de passagem livre são resultados calculados e revisáveis, não valores normativos presumidos.

## 12. Comportamento frente à parede, geometria e interseções

| Operação no hospedeiro | Comportamento obrigatório |
|---|---|
| Transladar/girar parede | Porta e abertura acompanham, com referência preservada |
| Alterar comprimento | Porta e abertura conservam ID/params; corte visível é a interseção possível com a parede |
| Recuar extremidade atravessando porta | Não excluir porta automaticamente; marcar como parcialmente/totalmente fora e permitir recuperação ao alongar |
| Alterar vértice / transformar parede em arco | Recalcular tangente, posição e orientação; não recriar GUID |
| Alterar altura | Corte é limitado pela parede existente; preservar altura nominal da porta e informar conflito |
| Alterar espessura/camadas | Recalcular encaixe automático do batente e requadro, preservar face de referência |
| Desfazer edição da parede | Porta, vão, IDs, posição e estado gráfico voltam de forma atômica |
| Mover porta na parede | Transladar parâmetro de estação, sem mover parede nem gerar segundo vão |
| Trocar âncora | Não mover fisicamente a porta; reinterpretar estação segundo centro/esquerda/direita |
| Mudar largura | Recalcular abertura e componentes respeitando âncora e folgas |
| Excluir porta | Excluir a instância e **seu vão**, reconstituir parede; Undo restaura ambos |
| Excluir parede hospedeira | Política técnica: avisar dependentes; ao confirmar, remover conjunto hospedado na mesma transação, não deixar vínculos órfãos |

A porta e sua folha podem continuar representadas como componente físico mesmo se a parede recuar temporariamente e o vão lógico ficar fora do trecho atual; o painel assinala condição `Fora da parede` e a vista não desenha corte onde não há parede. **Não deslocar automaticamente a porta para dentro** porque isso altera a intenção do projeto. Se geometria inválida impedir malha estanque, rejeitar somente a confirmação específica, preservando o estado anterior e a prévia sem travamento.

Paredes curvas: a abertura retangular é parametrizada no percurso da parede e a porta situa-se no plano tangente local; para larguras elevadas/raios pequenos o encaixe pode exigir aviso de folgas laterais e variação de profundidade. Parede curva multicamada, inclinação e nichos de correr embutidos têm gates específicos, nunca suporte presumido sem teste.

## 13. Porta independente e conversão hospedada

**Inserção livre:** instância `host_mode=free`, sem `host_id/opening_id`, com transformação 3D, `level_id`, offset, família e componentes. Pode ser duplicada, alinhada, rotacionada, ter ângulo/sentido e materiais editados. **Não recorta parede** nem cria abertura oculta.

**Converter livre → hospedada:** comando `Vincular a parede` mostra prévia do local, aplica as mesmas regras de inserção, verifica compatibilidade, cria novo registro de abertura e associa o mesmo `door_uid` e IFC GUID de porta. Preserva tipo, materiais, tamanho, orientação quando compatível; novo host/opening GUID é criado apenas para a relação geométrica recém-existente. Uma operação de Undo restaura a instância livre e remove o vão; Redo refaz vínculo com IDs coerentes.

**Converter hospedada → livre:** comando `Desvincular da parede` remove o recorte e a associação, mantendo porta e sua transformação mundial estáveis; não é o mesmo que **Excluir porta**. Ao contrário da exclusão aprovada, a desvinculação é uma operação intencional distinta com rótulo próprio. Evitar autovincular ao arrastar sobre paredes. Relações não são duplicadas no IFC.

## 14. Substituição de tipo, favoritos e parâmetros de usuário

Ao trocar modelo/família, manter `door_uid`, GUID, posição, cota, dimensões nominais, vínculo, face de referência, materiais e dados BIM **quando o novo tipo oferecer campos compatíveis**. Parâmetros incompatíveis são omitidos do novo tipo e mantidos em registro de migração recuperável/Undo; por exemplo, trocar porta de abrir por correr desativa dobradiça e converte orientação em lado de recolhimento por regra documentada. Se conversão produzir geometria inválida, prévia com alerta e não confirmação silenciosa. Perfil de família define folgas iniciais; cada instância admite override específico.

`Último tamanho usado`: estado exclusivo da sessão atual da ferramenta para inserir portas consecutivas iguais, independente das dimensões das portas já criadas; primeira ativação sem histórico utiliza preset inicial (decisão técnica: 0,90 × 2,10 m). Ao escolher novamente a porta padrão, aplicam-se as medidas padrão (0,90 × 2,10 m); somente a inserção contínua na mesma ferramenta conserva os últimos valores da sessão. As dimensões de cada porta colocada são próprias da instância, persistidas no `.igz` e no IFC, e nunca alteram a família, os presets ou as outras portas. Preferência de âncora é centro por padrão e não muda ao selecionar portas antigas. Favoritos são conjuntos reutilizáveis de parâmetros com `preset_id` e versão; **não** copiam GUID de instâncias existentes. Projeto deve abrir e operar offline, sem dependência de catálogo remoto.

## 15. Persistência, compatibilidade e migrações

Contrato implementado no P0 (`schema=2` somente para porta; janela permanece em `schema=1`). Nomes históricos de chaves são preservados, sem sinônimos:

```text
DoorInstance {
  schema=2; id; kind="door"; ifc_global_id?;
  family_key; host_mode="hosted"|"free";
  host_id?; opening_id?; anchor; position; sill;
  width; height; unit_width; unit_height;
  clearance_left; clearance_right; clearance_top; clearance_bottom;
  frame_thickness; leaf_thickness; hinge; swing;
  plan_angle; model_angle; name; type_name?; material_name?;
  original_extension_data (demais chaves desconhecidas, sem perda);
}
```

Persistir IDs estáveis; referências para tipo/família e materiais; transformações, mudanças do perfil da parede, vínculo de abertura, propriedades por componente e overrides. O arquivo `.igz` deve manter as portas após salvar/reabrir, inclusive favoritos incorporados ao projeto, sem converter geometria paramétrica para mesh morta.

**Migração obrigatória do contrato experimental atual (schema 1):** os registros atuais têm `host_id/opening_id` obrigatórios, `width/height` diretamente associados ao corte e um único `open_angle`. Ao migrar porta existente: preservar **exatamente o corte, a posição, a representação e os GUIDs anteriores**; inicializar folgas em zero ou em valores equivalentes compatíveis para não alargar recortes antigos; mapear ângulo antigo para `plan_angle` **e** `model_angle` de instâncias existentes para evitar salto visual; aplicar o novo padrão 90°/0° somente às **novas instâncias**. Versão antiga desconhecida deve ser carregada sem destruição de metadados, ou rejeitada com diagnóstico seguro. Migração deve poder ser testada com fixtures de projetos reais.

## 16. IFC e interoperabilidade

**Porta hospedada:** exportar `IfcWall`/elemento apropriado para hospedeiro, `IfcOpeningElement` para abertura, `IfcDoor` para instância, `IfcRelVoidsElement` entre parede e abertura, `IfcRelFillsElement` entre abertura e porta. Associar tipo em `IfcDoorType` quando suporte de esquema/exportador permitir, com dimensões e operação coerentes. `IfcRelFillsElement` é relação semântica entre vão e elemento de preenchimento, não artifício de renderização. **Não duplicar produtos IfcDoor** quando o elemento 3D já possui representação. Ver documentação buildingSMART.

**Porta livre:** exportar `IfcDoor` com colocação espacial e atributos, **sem inventar** `IfcOpeningElement`, `IfcRelVoidsElement` ou `IfcRelFillsElement`. Se vinculada depois, criar relações mantendo GUID da porta. **Porta composta:** por padrão uma instância IfcDoor com a forma e os parâmetros do conjunto; subcomponentes só viram entidades IFC separadas em modo avançado respaldado por regra explícita. Para tipos de operações especiais, preferir enums definidos no esquema IFC-alvo; quando não houver, usar classificação/atributo próprio sem falsear o tipo.

Exportação requer ao menos: GUIDs estáveis; dimensão nominal e dimensão bruta identificadas semanticamente; número de folhas, operação/handing quando aplicável; materiais e Psets estruturados; geometria com coordenadas coerentes; relação com pavimento e hospedeiro; sem produto ou abertura duplicado. Provar com inspeção programática e abertura em ao menos um visualizador IFC externo; o formato/esquema de exportação definitivo segue a compatibilidade do motor IFC do OpenTrace.

### Errata de implementação P1a (13/10/2026)

O contrato IFC desta etapa segue o padrão onde houver campo nativo: `IfcDoor.OverallWidth` e `IfcDoor.OverallHeight` recebem as dimensões **brutas do corte** (`wallhole_size`, metros), não as dimensões da folha. `IfcDoor.PredefinedType=DOOR` e `OperationType=SINGLE_SWING_LEFT` ou `SINGLE_SWING_RIGHT` refletem a orientação local: dobradiça à esquerda com giro positivo (ou à direita com giro negativo) produz LEFT; a combinação oposta produz RIGHT.

O Pset exclusivo `OpenTrace_Door` guarda os valores **da instância**, sem alterar a família:

| Propriedade IFC | Valor | Unidade |
|---|---|---|
| `LeafWidth`, `LeafHeight` | `width`, `height` da folha | metros |
| `ClearanceLeft`, `ClearanceRight` | `clearance_left`, `clearance_right` | metros |
| `ClearanceTop`, `ClearanceBottom` | `clearance_top`, `clearance_bottom` | metros |
| `PlanAngle`, `ModelAngle` | ângulos independentes | graus |
| `Family` | `F01 swing_single` | texto |
| `Schema` | `2` | inteiro |

`Pset_DoorCommon` contém apenas os valores existentes e explicitamente fornecidos, nunca inferidos; um arquivo sem `IsExternal` informado não recebe esse valor artificialmente. A porta física conserva uma única entidade `IfcDoor` conectada por `IfcRelFillsElement` ao `IfcOpeningElement` existente. A representação geométrica própria da abertura não é implementada na P1a, e os perfis externos continuam com os controles atuais de Voids/Fills.

## 17. Segurança de geometria, conflitos e feedback

**Política aprovada:** avisar sobre sobreposições e permitir confirmar quando a geometria resultante é válida. **Limite técnico obrigatório:** não autorizar malha inválida, componente sem espessura física, IDs repetidos, relação com abertura inexistente, cavidade embutida irrealizável ou operação que corrompa a cena. Mensagens indicam objeto/causa e possível correção. Ex.: `Porta P04: o nicho de correr precisa de comprimento de parede maior do que o disponível`.

Durante preview: cor normal para válido, alerta semântico para conflito confirmável e estado de bloqueio para inválido; estilo adaptado aos temas claro/escuro. Avisos não devem gerar `QMessageBox` a cada movimento. Confirmar uma sobreposição tolerável registra um estado de alerta no objeto/tabela para revisão. Testes de interseção incluem portas adjacentes, parede com múltiplos vãos, cunhas em paredes curvas, fim de parede, piso/forro, junta de paredes e duas folhas abrindo em conflito. Não implementar detecção perfeita entre todos os objetos BIM como pré-requisito para a primeira porta simples; identificar escopo verificado de cada gate.

## 18. Desempenho, Undo, seleção e preservação do viewport

Movimento de mouse atualiza apenas prévia leve e símbolos/cotas; criar malha definitiva ocorre na confirmação ou em edições commitadas. Mudanças de dimensões devem disparar um comando por confirmação (ou uma transação agregada), não dezenas de operações de histórico por pixel. Arraste termina com uma única edição e suporta `Esc` sem deixar alteração parcial. Quando houver múltiplas portas, a atualização de uma não pode sobrescrever parâmetros de outra. A interface deve sobreviver ao ciclo criar → editar → editar novamente → mudar parede → Undo/Redo → salvar/reabrir, inclusive com seleção ativa. Nunca reintroduzir o defeito anterior de viewport ao recuar parede perto de abertura. Cache de representação pode ser reconstruído por versão de geometria, material, tipo de vista e escala; invalidação não modifica propriedades BIM.

## 19. Plano de implementação em blocos testáveis

O escopo final é completo, mas a entrega é progressiva, **reaproveitando o código comprovado**. Blocos paralelos só quando os contratos entre os módulos são definidos, seguindo o caderno mestre.

| Bloco | Entrega observável | Dependências/Gate |
|---|---|---|
| **P0 — Contrato e migração** | Modelo de dados, medidas nominal/bruta/folha, ângulos independentes, compatibilidade schema 1, testes de dados | Sem regressões no código existente |
| **P1 — Abrir simples completa** | Dois cliques, face automática/Tab, âncora centro, modelo 3D, folha/arco independentes, excluir conjunto, propriedades e faixa | Paredes/aberturas estáveis, teste real no Windows |
| **P2 — Dupla e correr aparente** | Famílias F02/F03, folhas e deslizamento; ferragens LOD e materiais por componente | Editor especializado, medições e cotas |
| **P3 — Correr embutida REAL** | Câmara física, camadas/requadro, trilhos, estabilidade topológica e Undo | Motor de parede multicamada e testes de recuo/junções |
| **P4 — Composta** | Bandeiras/laterais/painéis, parametrização por subcomponentes, representação/IFC | F01/F02 + componente construtivo generalizado |
| **P5 — Porta livre + associação** | Criar livre, mover/rotacionar, vincular/desvincular com identidade estável | Contrato hosted/free e transações atômicas |
| **P6 — Fechamento BIM** | Vistas/LOD, biblioteca/favoritos, migração `.igz`, IFC e documentação de uso | Testes interoperáveis e aceite visual; outras famílias depois |

**Decisão técnica sobre ordenação:** P5 pode caminhar junto de P2/P3 quando contratos estabilizarem, não precisa aguardar composta se a implementação for independente. Pivotantes vêm **depois** de composta; sanfonadas/especiais após isso. A implementação de telas não substitui o motor geométrico; tampouco CI verde substitui aceite visual no Windows. Janelas continuam outra frente e podem reutilizar contratos, sem embaralhar suas características com as de portas.

## 20. Critérios objetivos de aceitação (checklist)

Legenda: `A` = teste automatizado, `W` = validação manual no IngeTrazo Windows, `I` = IFC externo. **“Pronto” exige o conjunto de testes indicado, não só existência de código.**

| ID | Cenário | Critério de aceite | Gate |
|---|---|---|---|
| PT-01 | Iniciar porta sobre parede sem pré-seleção | Preview identifica parede e face sem alterar cena | A/W |
| PT-02 | Inserir dois cliques | Primeiro fixa posição/face; segundo quadrante escolhe dobradiça/sentido | A/W |
| PT-03 | Tab antes do primeiro clique | Inverte face da referência e visualiza prévia correta | W |
| PT-04 | Cancelamento | `Esc` remove preview sem abertura órfã | A/W |
| PT-05 | Inserção contínua | Segunda porta reutiliza último tamanho, âncora centro; IDs diferentes | A/W |
| PT-06 | Redimensionar pela âncora | Centro preservado; dimensões/cotas atualizadas; folga consistente | A/W |
| PT-07 | Largura nominal ≠ vão bruto | Folgas por família/override alteram corte sem falsear passagem livre | A/W |
| PT-08 | Planta 90°, 3D fechado | Arco gira na planta e folha não gira no 3D; editar um não altera outro | A/W |
| PT-09 | Inverter giro | Altera lado de abertura, sem espelhar batente/face ou dobradiça | A/W |
| PT-10 | Espelhar dobradiça | Troca pivô sem mudar indevidamente a face da referência | A/W |
| PT-11 | Hotspots sucessivos | Editar mesmo ponto/aresta repetidamente, Undo/Redo funcionando | A/W |
| PT-12 | Mover/encurtar/reestender parede | Mantém IDs e restaura recorte quando trecho volta | A/W |
| PT-13 | Alterar altura/espessura/camadas | Batente segue espessura acabada; altura não destrói parede baixa | A/W |
| PT-14 | Abrir dupla | Folha ativa/passiva, medidas e arcos corretos | A/W |
| PT-15 | Correr aparente | Painel desliza sem recorte falso no trecho de recolhimento | A/W |
| PT-16 | Correr embutida | Nicho/camadas realmente alterados, malha fechada, Undo restaura | A/W |
| PT-17 | Correr embutida incompatível | Bloqueio específico sem destruir parede | A/W |
| PT-18 | Composta | Bandeira/laterais ajustam independentemente; conjunto mantém ID | A/W |
| PT-19 | Guarnições e materiais | Duas faces simétricas por padrão, material por lado e ocultação independente | A/W |
| PT-20 | Substituir família | Guarda parâmetros compatíveis; não troca GUID; conflito avisa | A/W |
| PT-21 | Excluir porta | Folha, batente, preenchimento e vão removidos numa operação; Undo restaura | A/W |
| PT-22 | Criar livre | Não cria abertura nem host falso | A/W/I |
| PT-23 | Livre → hospedada → Undo | Mesma porta/GUID, abertura nova vinculada, retorno livre coerente | A/W/I |
| PT-24 | Vista/escala | Planta, corte, elevação e 3D apresentam LOD/símbolos corretos | W |
| PT-25 | Sincronização UI | Barra ↔ paleta ↔ modelo; seleção não inicia nova criação | A/W |
| PT-26 | Salvar/reabrir `.igz` | Preserva todas as propriedades, materiais, ID, ângulos e vínculos | A/W |
| PT-27 | Migrar porta antiga | Mantém corte/posição/IDs/ângulo visual antigo sem aumento por folgas novas | A/W |
| PT-28 | Exportar IFC hospedada | Uma IfcDoor, uma abertura, Voids/Fills corretos; sem duplicata | A/I |
| PT-29 | Exportar IFC livre | IfcDoor espacial sem IfcOpening/relacionamento falso | A/I |
| PT-30 | Regressão gráfica | Sem corrupção da viewport/arestas fantasmas em seleção + recuo + Undo | W |

**Gate de aceite independente:** testes unitários e host offscreen podem qualificar o motor, mas a interface só estará aceita após captura/teste real no IngeTrazo Windows com controles legíveis, painéis flutuantes sobre a vista, paleta renovada e interações de mouse corretas.

## 21. Fora de escopo da primeira entrega e decisões técnicas automáticas

**Não exigir na F01 inicial:** mecanismo completo de ferragens, catálogo de fabricantes sincronizado pela internet, pivotantes, sanfonadas, renderização foto-realista, checagem automática de toda norma de acessibilidade, detecção universal de colisões, suporte geométrico garantido para nichos em qualquer parede curva/perfil arbitrário. Esses itens não serão anunciados como prontos sem implementação e teste.

**Decisões técnicas menores encerradas sem consulta adicional:** parâmetros internos em unidades SI; schemas versionados e migrações não destrutivas; fluxo sem nuvem; presets locais; orientação por eixos locais da parede; defaults de primeira utilização 0,90 × 2,10 m; componentes com IDs estáveis; desempenho com prévia temporária; modelo baseado em comandos de histórico; mensagens contextualizadas; documentação e testes automatizados por bloco. Não adicionar quarta rodada de perguntas.

## 22. Estado real do projeto na data da especificação

Referência histórica da redação original: branch `dev/opening-controller-integration-2026-10-10`, repositório `lelopes05/opentrace-bim`, **em leitura**. Estado atualizado em 13/10: a porta já é ferramenta do host (etapa 1), com âncora padrão central. A branch-base do P0 é `claude/b1-curved-wall-perf` (`5df646e`) e o trabalho do P0 ocorre apenas em `gpt/portas-p0`:

- `OpenTrace_BIM/door_window_core.py`: contrato inicial com esquerda/centro/direita, por padrão **esquerda**, largura/altura diretamente atreladas ao vão, `host_id/opening_id` obrigatórios, uma variável `open_angle`, `swing`, `hinge` e seis hotspots.
- `OpenTrace_BIM/door_window_geometry.py`: geometria de porta simples com três peças de marco e folha prismática; rotação 3D usa `open_angle` atual; não é catálogo completo.
- `OpenTrace_BIM/door_window_commands.py`: comandos hospedados atômicos, inclusive criação, edição, inversão e `DeleteHostedOpening` que remove recorte e preenchimento juntos.
- `docs/DECISIONS.md`: a fileira de ferramentas e o painel de opções flutuam sobre a vista (decisão de 13/10); versão recente de interface segue **pendente de homologação visual no Windows**.
- `docs/DEVELOPMENT_MASTER.md`: preservar arquitetura de aberturas separadas de objetos preenchendo o vão, IDs e IFC; desenvolvimento das portas é **etapa 02**, interface em frente paralela.

Portanto a especificação **não** representa desenvolvimento já executado de portas duplas, portas livres, nichos de correr, materiais independentes ou IFC completo. Nenhum teste de runtime foi realizado nesta tarefa e **nenhum arquivo do repositório foi alterado**.

## 23. Referências verificáveis

- Caderno mestre do projeto: <https://github.com/lelopes05/opentrace-bim/blob/dev/opening-controller-integration-2026-10-10/docs/DEVELOPMENT_MASTER.md>
- Caderno mestre da interface: <https://github.com/lelopes05/opentrace-bim/blob/dev/opening-controller-integration-2026-10-10/docs/INTERFACE_MASTER.md>
- Núcleo atual de portas: <https://github.com/lelopes05/opentrace-bim/blob/dev/opening-controller-integration-2026-10-10/OpenTrace_BIM/door_window_core.py>
- Geometria experimental: <https://github.com/lelopes05/opentrace-bim/blob/dev/opening-controller-integration-2026-10-10/OpenTrace_BIM/door_window_geometry.py>
- Comandos experimentais: <https://github.com/lelopes05/opentrace-bim/blob/dev/opening-controller-integration-2026-10-10/OpenTrace_BIM/door_window_commands.py>
- Archicad, documentação de tamanhos nominais e tolerância: <https://help.graphisoft.com/AC/26/BRA/_AC26_Help/150-1_DoorWindowCustomSettings/150-1_DoorWindowCustomSettings-2.htm>
- buildingSMART, `IfcRelFillsElement`: <https://standards.buildingsmart.org/IFC/RELEASE/IFC4/FINAL/HTML/schema/ifcproductextension/lexical/ifcrelfillselement.htm>
- buildingSMART, `IfcDoorType`: <https://standards.buildingsmart.org/IFC/RELEASE/IFC4/FINAL/HTML/schema/ifcsharedbldgelements/lexical/ifcdoortype.htm>

---

**Regra de encerramento:** especificação funcional e roteiro de aceitação fechados. Qualquer divergência futura comprovada por teste deve ser tratada como defeito, restrição técnica ou mudança de escopo registrada, **não como pretexto para reabrir indefinidamente a descoberta de requisitos**. Implementação e alterações no GitHub dependem de autorização posterior e são tarefas separadas desta especificação.