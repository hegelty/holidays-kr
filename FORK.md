# 독립 호스팅 포크 운영

## 목표와 의존성

- 조회 시 원저자의 도메인, npm CDN, 공공데이터 API를 호출하지 않습니다.
- Pages 빌드·배포는 저장소에 커밋된 JSON과 Node.js 기본 모듈만 사용합니다.
  `pnpm install`, API 키, 별도 서버가 필요 없습니다.
- **새 데이터의 자동 수급은 `hyunbinseo/holidays-kr`에 의존합니다.**
  원본 장애 시 갱신 작업은 실패하지만, 이미 배포한 파일은 그대로 제공됩니다.
- GitHub Actions와 GitHub Pages 자체의 장애까지 제거하는 구성은 아닙니다.
  `_site` 산출물은 다른 정적 웹 서버에도 그대로 옮길 수 있습니다.
- 날짜·형식 검증은 데이터의 법적 정확성을 보증하지 않습니다.
  임시공휴일 등을 직접 수정할 때는 공식 발표를 별도로 확인합니다.

## 최초 설정

1. 이 저장소를 본인 계정으로 Fork합니다. 기본 브랜치는 `main`을 사용합니다.
2. **Actions**에서 포크의 워크플로를 활성화합니다.
3. **Settings → Pages → Build and deployment → Source → GitHub Actions**로 설정합니다.
4. **Actions → Update and deploy Pages → Run workflow**를 실행합니다.
   원본 갱신 없이 로컬 스냅샷만 배포하려면 `sync`를 해제합니다.
5. **Settings → Pages → Custom domain**에 `holidays.hegelty.me`를 입력합니다.
   DNS 확인과 인증서 발급이 완료되면 **Enforce HTTPS**를 켭니다.
   루트의 `CNAME`도 같은 도메인으로 설정되어 있으며 배포 산출물에 포함됩니다.
6. Pages 배포 결과에서 사이트 주소를 확인합니다.

이 포크의 서비스 주소는 **https://holidays.hegelty.me/** 입니다.
전체 캘린더 구독 주소는 **https://holidays.hegelty.me/basic.ics** 입니다.

일반적인 프로젝트 사이트 주소는 `https://<계정>.github.io/<저장소>/`입니다.
사이트의 JSON·CSV·ICS 링크는 상대 경로여서 저장소 이름이나 사용자 지정 도메인에
종속되지 않습니다. 외부 글꼴, 스크립트, 스타일시트도 사용하지 않습니다.

```js
// API 키 불필요.
const base = 'https://holidays.hegelty.me/';
const response = await fetch(new URL('2026.json', base));
if (!response.ok) throw new Error(`HTTP ${response.status}`);
const holidays = await response.json();
console.log(holidays['2026-01-01']); // ['1월 1일']
```

- `basic.json`: `{ "2026": { "2026-01-01": ["1월 1일"] }, ... }`
- `2026.json`: `{ "2026-01-01": ["1월 1일"], ... }`
- `basic.ics`: 전체 연도 캘린더 구독 주소
- `2026.csv`, `2026.ics`: 연도별 다운로드
- `anniversaries/`: 공휴일과 별개인 기념일의 동일 형식
- `status.json`: 데이터 커밋 시각, 지원 연도, 내용 SHA-256

## 자동 갱신과 실패 처리

매일 KST 06:23에 갱신을 시도합니다. 스케줄 실행은 지연될 수 있습니다.

1. 원본 `main`의 `public`만 별도 디렉터리로 가져옵니다.
2. `basic.json`, `anniversaries/basic.json`만 읽습니다. 원본 코드·워크플로는 실행하거나 병합하지 않습니다.
3. 빈 데이터, 잘못된 날짜, 중복 명칭, 제어 문자, 기존 지원 연도 누락을 거부합니다.
4. 변경이 있을 때만 JSON·CSV·ICS와 라이브러리의 TypeScript 프리셋을 함께 갱신하고 커밋합니다.
   커밋 메시지에 원본 커밋 SHA를 남깁니다.
5. 같은 실행 안에서 갱신된 `main`을 다시 체크아웃해 Pages에 배포합니다.
   봇 커밋이 후속 push 워크플로를 실행해 줄 것이라고 가정하지 않습니다.

검증·빌드·push가 실패하면 배포 작업을 실행하지 않습니다. 기존 사이트는 유지되며
Actions 실행 로그에서 원인을 확인합니다. 기존 연도를 삭제하려면 자동 갱신이 아니라
직접 검토한 변경이 필요합니다. 개별 공휴일의 정정·삭제는 허용합니다.

포크의 로컬 데이터 수정은 다음 동기화 때 원본 내용으로 덮어씁니다.
독자적으로 데이터를 관리하려면 스케줄을 제거하고 수동 실행의 `sync`를 해제하세요.
`public/basic.json`과 `public/anniversaries/basic.json`이 Pages 빌드의 입력입니다.
기존 npm 라이브러리를 함께 관리한다면 `src` 프리셋도 함께 수정해야 합니다.

브랜치 보호 규칙이 봇의 직접 push를 금지하면 갱신은 실패합니다.
그 경우 저장소 정책에 맞는 PR 기반 갱신으로 바꿔야 합니다.
공개 저장소의 장기간 비활동이나 포크 설정으로 예약 실행이 비활성화될 수 있으므로
Actions 상태와 실패 알림을 주기적으로 확인하세요.

## 로컬 검증

Node.js 22 이상과 Git만 필요합니다.

```sh
node --test scripts/pages.test.mjs
node scripts/pages.mjs build
# _site/를 정적 웹 서버로 제공

# 별도로 가져온 원본 체크아웃의 데이터로 갱신
node scripts/pages.mjs sync /path/to/upstream/public
```

빌드는 네트워크 요청을 하지 않으며 커밋된 `public`의 마지막 변경 시각을 사용하여
동일 커밋에서 재현 가능한 산출물을 생성합니다.
기존 이벤트 UID를 유지하고 ICS에는 CRLF, UTF-8 줄 접기, 종료일을 적용합니다.

원본 패키지 개발용 pnpm·TypeScript·Vitest 도구는 그대로 남겨 두었지만 Pages에는
사용하지 않습니다. 원본 npm 패키지로 잘못 배포하지 않도록 포크에서는 npm 게시 작업을
건너뜁니다. 이 포크를 별도 npm 패키지로 배포하려면 이름·저장소 메타데이터·게시 설정을
먼저 바꾸어야 합니다. 원저작자의 MIT 라이선스는 유지합니다.
