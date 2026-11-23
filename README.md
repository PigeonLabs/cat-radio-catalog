# 고양이 라디오 방송국 카탈로그

매주 월요일 09:17 KST에 GitHub Actions가 Radio Browser 미러의 해외 목록과 국내 검수 목록을 결합해 검사합니다. 국내 방송국과 백업 주소는 `data/korea.csv`에서 수정합니다. 해외 생성기는 지난 배포본의 방송 ID와 별칭을 이어받습니다. 원본 수집이나 검증에 실패하면 마지막 공개 Release가 유지됩니다.

앱은 `releases/latest/download/manifest.json`으로 버전을 확인하고 태그에 고정된 국내·해외 파일을 내려받습니다. 스키마 1의 파일별 SHA-256은 압축된 바이트 기준입니다. 수동 갱신은 Actions의 **Weekly radio catalog → Run workflow**에서 실행합니다.

공개 저장소는 60일간 활동이 없으면 GitHub가 예약 실행을 비활성화할 수 있습니다. Actions에서 워크플로 상태와 마지막 성공 실행을 확인하고 필요한 경우 다시 활성화하세요.
