# Gerador de apex_v00_36_0_master_full.txt — APPEND (novos módulos OPP-125 a OPP-132)
# Executa DEPOIS de gen_v0036.py
# Lê módulos de arquivo separado para evitar conflito de aspas

path = "C:/Users/Thiag/Downloads/apex_v00_36_0_master_full.txt"
modules_path = "C:/Users/Thiag/Downloads/v00_36_modules.txt"

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()
print(f"Atual: {content.count(chr(10))+1} linhas")

with open(modules_path, 'r', encoding='utf-8') as f:
    new_modules = f.read()
print(f"Módulos a adicionar: {new_modules.count(chr(10))+1} linhas")

content = content + "\n" + new_modules

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

lines = content.count('\n') + 1
print(f"Final: {lines} linhas, {len(content)} chars")
print(f"Arquivo: {path}")

# Verificação
checks = {
    "v00.36.0 header":           "v00.36.0" in content,
    "SR_42 rule":                "SR_42" in content,
    "SR_43 rule":                "SR_43" in content,
    "SR_44 rule":                "SR_44" in content,
    "SR_45 rule":                "SR_45" in content,
    "verify_integrity":          "verify_integrity" in content,
    "forge_skill_with_integrity":"forge_skill_with_integrity" in content,
    "check_ghost_dependencies":  "check_ghost_dependencies" in content,
    "ApexLogger":                "ApexLogger" in content,
    "_redact_string":            "_redact_string" in content,
    "apex_creation_guide":       "apex_creation_guide" in content,
    "community_agent_normalization": "community_agent_normalization" in content,
    "OPP-125":                   "OPP-125" in content,
    "OPP-132":                   "OPP-132" in content,
    "127 DIFFs":                 "127" in content,
}

print("\n=== VERIFICAÇÃO ===")
all_ok = True
for k, v in checks.items():
    status = "OK  " if v else "FAIL"
    if not v:
        all_ok = False
    print(f"  {status}: {k}")

print(f"\n{'>>> SUCESSO — v00.36.0 gerado' if all_ok else '>>> ATENÇÃO — verificar itens FAIL'}")
