$ErrorActionPreference = "Stop"
Write-Host "한글문서 자동작성 엔진 설치 확인"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  throw "Python 3.10 이상을 먼저 설치하세요."
}
if (-not (Get-Command hwp -ErrorAction SilentlyContinue)) {
  Write-Host "hwp-cli가 아직 없습니다."
  Write-Host "GitHub STAIxBWLB/hwp-cli 최신 Windows release의 hwp 실행파일을 내려받아 PATH에 추가하세요."
  exit 2
}
python -m pip install -e .
Write-Host "설치 완료"
hwp --version
