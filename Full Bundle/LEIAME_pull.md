# APEX — Bundle FULL (todos os commits) — instruções de pull

Bundle git **completo e autocontido** de todo o repositório APEX (história inteira,
todos os commits, todas as branches/tags alcançáveis), particionado em 10 arquivos
de ≤24MB porque o canal limita anexos a 25MB.

- **Branch de trabalho:** `claude/analyze-apex-repository-BiVMP`
- **HEAD (commit no topo):** `bb803faeb342e42c33e16d3018c5381c3bb8b779`
- **SHA256 do bundle remontado:** `d0d6e1e70a8662f96af75c0616082b6487c951344b22655e8cdade6c70609229`

---

## 1) Baixe as 10 partes na MESMA pasta
```
apex_FULL.part_00  apex_FULL.part_01  ...  apex_FULL.part_09
```

## 2) Remonte o bundle (a ordem é garantida pelo `*` do shell)
**Linux / macOS:**
```bash
cat apex_FULL.part_* > apex_FULL.bundle
```
**Windows (PowerShell):**
```powershell
cmd /c "copy /b apex_FULL.part_00+apex_FULL.part_01+apex_FULL.part_02+apex_FULL.part_03+apex_FULL.part_04+apex_FULL.part_05+apex_FULL.part_06+apex_FULL.part_07+apex_FULL.part_08+apex_FULL.part_09 apex_FULL.bundle"
```

## 3) Verifique a integridade (opcional, recomendado)
```bash
sha256sum apex_FULL.bundle
# deve imprimir: d0d6e1e70a8662f96af75c0616082b6487c951344b22655e8cdade6c70609229

git bundle verify apex_FULL.bundle
# deve dizer "The bundle is okay" e listar os refs
```

---

## 4a) SE você AINDA NÃO tem o repositório — clone direto do bundle
```bash
git clone apex_FULL.bundle APEX
cd APEX
git checkout claude/analyze-apex-repository-BiVMP
```

## 4b) SE você JÁ tem o repositório — puxe do bundle para o seu clone
```bash
cd /caminho/do/seu/APEX

# registra o bundle como um remote temporário
git remote add bundle /caminho/para/apex_FULL.bundle    # ou: git bundle unbundle

# traz todos os refs do bundle
git fetch bundle

# leva o trabalho para a SUA main (fast-forward se possível, senão merge)
git checkout main
git merge bundle/claude/analyze-apex-repository-BiVMP

# limpa o remote temporário
git remote remove bundle
```

> Alternativa direta sem remote:
> ```bash
> git fetch apex_FULL.bundle claude/analyze-apex-repository-BiVMP:refs/heads/apex-work
> git checkout main
> git merge apex-work
> ```

---

## 5) Enviar para o `main` remoto (quando você tiver permissão de push)
No ambiente atual o push é bloqueado pela política da org (403), por isso a entrega
é por bundle. No SEU terminal, com credenciais válidas:
```bash
git checkout main
git merge bundle/claude/analyze-apex-repository-BiVMP   # ou apex-work
git push origin main
```

## Notas
- O bundle é **autocontido**: contém toda a história, então funciona mesmo num
  clone novo (item 4a), sem depender do GitHub.
- Se `git merge` acusar divergência, use `git log --oneline --graph main bundle/claude/analyze-apex-repository-BiVMP`
  para inspecionar; o HEAD do bundle (`bb803fae`) deve estar à frente da sua main.
- Todos os commits têm mensagens descritivas por sprint (CD…CY) e o rodapé
  `Co-Authored-By` / `Claude-Session`.
