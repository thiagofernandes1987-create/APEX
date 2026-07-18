# Sprint AS — motor AST M9.2 estendido a Rust; fecha diesel (#62)

> Continuação direta de AR. Tese: o motor de diff estrutural AST (M9.2)
> não é específico de C — generaliza para qualquer gramática tree-sitter
> pip-instalável. Aplicado aqui aos 2 gaps reais da categoria Rust
> (56-65), que estava 8/10.

## Identificação precisa dos gaps de Rust

Cobertos antes desta sprint (8): #56 rust-lang/rust, #57 tokio, #58
alacritty, #60 nushell, #61 tikv, #63 swc, #64 actix-web, #65 tauri.
**Faltavam: #59 serde, #62 diesel.**

## #62 diesel-rs/diesel — FECHADO via SAST AST-anchored

Fix de soundness real: commit `c9776e384f52` ("Remove the unsound
`SerializedDatabase::new` function"), pai `7a57b3f616f4`, arquivo único
`diesel/src/sqlite/connection/serialized_database.rs` (+4-1).

Diff AST (gramática `tree_sitter_rust`):

| métrica | antes | depois |
|---|---|---|
| nós totais | 263 | 283 |
| **`unsafe`** | **2** | **3** |
| `function_modifiers` | 0 | 1 |
| churn total | — | **20** |

O sinal decisivo é o `unsafe` 2→3 / `function_modifiers` 0→1: o fix
tornou a construção `unsafe`, transferindo formalmente o contrato de
soundness (memory-safety) para o chamador. É exatamente o tipo de fix
de segurança de Rust que um adapter regex não capturaria como sinal,
e que o eixo AST torna mensurável. Dado SAST AST-anchored legítimo.

## Validação cruzada — #56 rust-lang/rust CVE-2024-24576 (BatBadBut)

`rust-lang/rust` já tinha eixo SCA (Cargo.lock, rating B). Mesmo assim,
rodamos o motor AST no fix da CVE-2024-24576 (escaping de argumentos de
`Command` no Windows), merge `8b2459c1f211` vs. pai `033becf83c62`,
arquivo `library/std/src/sys/pal/windows/args.rs`:

- churn = **640**; `if_expression`+9, `binary_expression`+10, `==`+5,
  `||`+4, `>`+2, `<`+2.

Não adiciona repo novo (já contado), mas confirma que o motor AST produz
sinal forte e coerente num fix de segurança Rust de larga escala — não
só nos casos pequenos.

## #59 serde — gap honesto remanescente

`serde-rs/serde` é biblioteca de serialização sem CVE/RUSTSEC de
memory-safety indexada: busca de commits por `CVE`/`RUSTSEC` retornou 0;
`overflow`/`panic` retornam ruído de issues comuns, não um fix de
vulnerabilidade ancorável. Sem lockfile (é lib). Permanece sem eixo —
documentado honestamente, não forçado.

## Resultado

Categoria Rust **8/10 → 9/10**. Total da lista master **75 → 76/100**.
Restam 24/100, agora com roadmap pesquisado (Sprint AR) em vez de "teto":
Python (7), Rust (1: serde), Java/Kotlin (4), PHP/Ruby/C#/Mobile (5),
Infra (2), C/C++ (3: sqlite reservado, httpd/wireshark sem fix-commit
localizável). O motor AST agora cobre C/C++/PHP/Ruby/C#/Rust — próximas
avenidas: aplicá-lo aos fixes Java/Kotlin (grammar já presente p/ Java)
e Python restantes, e o SCA por similaridade de função (Sprint AT) para
os 5 sem lockfile.
