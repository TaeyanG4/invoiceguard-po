# 프로젝트 설정
`settings.json`은 기본 권한 모드와 일부 비밀 경로·원격 명령 규칙만 포함한다. hooks, plugins, MCP, agent 모델 강제 선택이나 자동 유료 실행은 없다.

실제 적용된 권한은 Claude Code의 `/permissions`에서 확인한다. 사용자/조직/local 설정과 도구 버전 때문에 실제 동작은 환경에서 검증해야 한다. 이 파일만으로 예산/비밀 유출/모든 shell 우회 경로가 통제되는 것은 아니다.

개인 변경은 `.claude/settings.local.json`에 두고 Git에 넣지 않는다. 자동 실행 스크립트를 추가하거나 권한 확인을 우회하는 설정을 넣지 않는다. 상세: [작업 방식](../docs/17_CLAUDE_CODE_WORKFLOW.md).
