# OpenTrace BIM 0.44.0 Rust

Cópia isolada da versão 0.44.0. O arquivo de origem fornecido pelo usuário
possui SHA-256 b03455f4c24b95592e4ce671bdb85eb60e06bff02a617bcc497d8697fa40a937,
igual ao ativo oficial da release v0.44.0. O GitHub Actions exige a conferência
dessa assinatura antes de gerar um novo pacote para Windows.

A primeira migração é o cálculo de alinhamento/distribuição de objetos em Rust.
A UI PySide6, seleção, undo/redo, paredes, portas, IFC e integração com IngeTrazo
permanecem em Python. O código original de arrange_core.py está preservado.

O pacote mantém a pasta OpenTrace_BIM e a versão interna 0.44.0 por
compatibilidade. A identificação visível é 0.44.0 Rust.

## Executar no Windows

1. Baixe o artefato "OpenTrace BIM 0.44.0 Rust" do workflow desta branch.
2. Extraia o ZIP com a pasta OpenTrace_BIM na pasta de plugins do IngeTrazo,
   após fechar o programa e salvar uma cópia da instalação anterior.
3. Para ativar o motor Rust, configure OPENTRACE_RUST_BACKEND=1 antes de abrir o
   IngeTrazo. Sem essa opção, continua sendo usado o Python original.
4. Confirme no painel do OpenTrace a identificação 0.44.0 Rust.
5. Teste alinhamento/distribuição de objetos, inclusive desfazer e refazer.

A biblioteca compilada fica em rust_core/target/release/opentrace_rust_core.dll.
Se Rust estiver explicitamente ativado e a DLL não existir, a operação
informará o erro em vez de executar silenciosamente o motor Python.

A compilação e os testes unitários/equivalência rodam no GitHub Actions.
A validação de interface real com IngeTrazo Windows é responsabilidade do usuário.

Não publicar release, alterar catálogo ou mesclar com main automaticamente.
