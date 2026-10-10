# Botão do humano — verifica a âncora L3 (corre no Windows, quando quiseres)
# Uso:  powershell -File Verificar-Ancora.ps1
#       (lê $HOME\Documents\vyra-ancora.txt — ficheiro que GUARDASTE do relatório,
#        fora do alcance do agente — e compara com os ficheiros atuais)
param([string]$Ancora = "$HOME\Documents\vyra-ancora.txt")
$mapa = @{
  "backend/app/core/firebase.py" = "C:\Users\franc\vyra\backend\app\core\firebase.py"
  "backend/app/core/agents.py"   = "C:\Users\franc\vyra\backend\app\core\agents.py"
  "backend/bot_state.json"       = "C:\Users\franc\vyra\backend\bot_state.json"
}
$esperados = @{}
Get-Content $Ancora | ForEach-Object {
  if ($_ -match "^([0-9a-f]{64})\s+(.+)$") { $esperados[$Matches[2].Trim()] = $Matches[1] }
}
$ok = $true
foreach ($chave in $mapa.Keys) {
  $atual = (Get-FileHash $mapa[$chave] -Algorithm SHA256).Hash.ToLower()
  $ref = $esperados[$chave]
  if ($null -eq $ref) { Write-Output "SEM-ANCORA: $chave"; $ok = $false }
  elseif ($atual -eq $ref) { Write-Output "OK: $chave" }
  else { Write-Output "ALTERADO: $chave"; $ok = $false }
}
# bot_state.json muda com o bot vivo — diferença aí é ESPERADA, não alarme.
Write-Output "---"
Write-Output "Para o Firestore: abre o console do Firebase, coleção indicacoes, e compara a contagem com o último snapshot em football-ai/snapshots/."
if ($ok) { Write-Output "VEREDITO: intacto" } else { Write-Output "VEREDITO: rever acima" }
