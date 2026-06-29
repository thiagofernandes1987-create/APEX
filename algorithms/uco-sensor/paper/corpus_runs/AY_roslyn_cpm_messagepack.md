# Sprint AY — Central Package Management; fecha roslyn (#89) com true-positive

> Fecha o near-miss de AX. roslyn usa NuGet **Central Package Management**:
> as versões não estão inline, mas indiretas via propriedades MSBuild.
> Resolvendo a indireção corretamente, o motor M9.4 produziu seu primeiro
> **achado vulnerável real**.

## A cadeia de indireção do roslyn

```
Directory.Packages.props  →  só <ManagePackageVersionsCentrally>true</...>
eng/Packages.props        →  <PackageVersion Include="MessagePack" Version="$(MessagePackVersion)" />
eng/Versions.props        →  <MessagePackVersion>2.5.198</MessagePackVersion>
```

`parse_msbuild_cpm` (novo no M9.4) junta `Packages.props` × `Versions.props`,
resolvendo `$(Var)` → versão. **Disciplina anti-FP:** variável sem
definição é descartada (nunca chuta), então uma indireção quebrada não
gera versão errada. Resultado: **123 pacotes resolvidos**.

## O true-positive: MessagePack 2.5.198

Dos 123, um é vulnerável — verificado contra os ranges reais do GHSA:

| CVE | range | 2.5.198 dentro? |
|---|---|---|
| CVE-2026-48517..48506, 48109 (11×) | `< 2.5.301` | **SIM** → vulnerável |
| CVE-2024-48924 | `< 2.5.187` | não (2.5.198 ≥ 2.5.187, já patched) |
| CVE-2026-485xx (variante) | `>= 3.0, < 3.1.7` | não (2.5.198 < 3.0) |
| CVE-2020-5234 | `< 1.9.11` | não |

A versão 2.5.198 está exatamente na **janela vulnerável**
`[≥2.5.187, <2.5.301]`: corrigida para a CVE de 2024 mas ainda exposta às
11 CVEs CVE-2026-485xx (patched só em 2.5.301). O range-matcher do M9.4
acerta a janela — **não** marca "tem CVE" cegamente. Rating **E**.

Este é o **primeiro achado vulnerável** do M9.4 (AW/AX deram vereditos
limpos). Demonstra que o motor é capaz de true-positives precisos, não só
de confirmar limpeza — exatamente a propriedade que diferencia SCA real de
um detector ingênuo de FP.

## Resultado

`dotnet/roslyn` (#89) **FECHADO** com eixo SCA (E, vulnerável).
Categoria PHP/Ruby/C#/Mobile 7/10 → **8/10**. Total **87 → 88/100**.

O motor M9.4 agora cobre 3 formatos de manifesto de versão resolvida:
- `composer` libs vendorizadas com `VERSION` (AW, wordpress)
- NuGet `packages.config` old-style (AX, shadowsocks)
- NuGet Central Package Management indireto (AY, roslyn)

Restam 12/100. Gaps PHP/Ruby/C#/Mobile: #93 jekyll (gemspec com ranges,
sem versão resolvida), #94 signal-android (sem lockfile gradle). Demais:
elasticsearch/redisson/kotlin/clickhouse/serde/boto3 (patch não
resolvível / sem grammar), httpd/wireshark (SVN/GitLab), sqlite
(reservado FP). De 74 a 88 nesta sessão, três motores, zero fabricação —
e agora com true-positives além de vereditos limpos.
