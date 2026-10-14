# F01 — composição paramétrica de folha (implementação experimental)

Branch de trabalho: `gpt/porta-folha-componentes`. Não há merge automático na main.

## Diagnóstico da base

Antes desta implementação, `door_window_core.py` oferecia três variantes
`plain`, `grooved`, `panelled`; `door_window_geometry.py` gerava
uma folha opaca inteira, inclusive quando criava frisos e almofadas de
acabamento. Montantes e vidros paramétricos existiam apenas no motor simples
de janelas. Não existiam divisórias reais de vidro para a **folha da porta**.

## Entrega

- Novo modo `leaf_variant="grid"` para a família F01 física, com
  `leaf_grid` persistido junto aos parâmetros da instância.
- Editor acessível em **Propriedades da porta → Composição paramétrica da
  folha → Editar montantes, travessas e painéis**. A tabela permite escolher
  por célula: vidro, painel sólido, veneziana de réguas ou vazio.
- Montantes laterais, travessas superior/inferior, montantes/travessas
  intermediários e todos os painéis são sólidos de malha separados; vidros
  não têm uma folha opaca por trás.
- Quantidades de 1 a 8 colunas/linhas; medidas independentes para montantes,
  travessas, vidro e painel. O editor valida disponibilidade geométrica.
- Material independente para montantes, travessas, vidro, painel e veneziana.
  Sem definição específica, estruturas usam o material da borda da folha;
  vidro usa material de aparência translúcida.
- Uma alteração do editor chama o mesmo `EditHostedFill`, preservando ID,
  IFC, vão da parede, grupo, associação hospedeira e Undo/Redo.
- Para outras três variantes, a geometria anterior é intocada; registros
  antigos não recebem uma grade automaticamente.

## Semântica do registro

```json
{
  "leaf_variant": "grid",
  "leaf_grid": {
    "columns": 2, "rows": 3,
    "stile_width": 0.08, "rail_width": 0.10,
    "mullion_width": 0.045, "transom_width": 0.045,
    "glass_thickness": 0.008, "panel_thickness": 0.018,
    "cell_types": ["solid", "solid", "glass", "glass", "glass", "glass"]
  }
}
```

Todas as medidas estão em metros. `cell_types` percorre as linhas da
base para o topo, da esquerda para a direita; a tabela apresenta o topo
na primeira linha para ficar familiar para o projetista.

## Limites declarados

- Disponível para porta de abrir simples F01 em layout físico; **não**
  habilita famílias F02–F08 nem altera o motor de janelas.
- Divisões são uniformes por coluna/linha; a próxima iteração pode adotar
  larguras/alturas individuais e perfis inclinados.
- Venezianas representam réguas paralelas horizontais (sem inclinação
  aerodinâmica, ensaio acústico ou ventilação normativa).
- O editor é de instância, não uma biblioteca de tipologias reutilizáveis.
- Aceite visual no Windows IngeTrazo permanece necessário além do CI.

## Validação

`tests/test_door_leaf_grid.py` e
`tests_host/test_door_leaf_grid_host.py` verificam modelo puro,
malhas no host real, regressões, histórico, persistência .igz e o editor.
