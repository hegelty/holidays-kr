# 독립 호스팅 포크 운영

[![데이터 갱신 및 배포](https://github.com/hegelty/holidays-kr/actions/workflows/pages.yml/badge.svg?branch=main)](https://github.com/hegelty/holidays-kr/actions/workflows/pages.yml)

## 구성

```text
한국천문연구원 특일 정보 API
  → Python 표준 라이브러리로 XML 수집·검증
  → Node.js로 JSON·CSV·ICS 및 TypeScript 프리셋 생성
  → 변경된 데이터만 저장소에 커밋
  → GitHub Pages 배포
  → holidays.hegelty.me
```

원본 프로젝트 저장소의 데이터나 코드는 갱신 시 가져오지 않습니다.
공식 API가 수집 단계의 유일한 외부 데이터 공급원입니다.
조회와 Pages 빌드는 저장소의 JSON만 사용하므로 API 키나 원저자의 서버가 필요 없습니다.
공식 API 및 GitHub 자체의 장애까지 제거하는 구성은 아닙니다.

## 최초 설정

1. 저장소의 기본 브랜치를 `main`으로 두고 **Actions**를 활성화합니다.
2. [한국천문연구원 특일 정보 API](https://www.data.go.kr/data/15012690/openapi.do)를 활용 신청합니다.
3. **Settings → Secrets and variables → Actions → New repository secret**에서
   `DATA_GO_KR_SERVICE_KEY`를 등록합니다. Encoding·Decoding 키 모두 입력할 수 있습니다.
   키는 채팅, 코드, 커밋 메시지, 이슈에 올리지 마세요.
4. **Settings → Pages → Build and deployment → Source → GitHub Actions**로 설정합니다.
5. **Custom domain**에 `holidays.hegelty.me`를 설정하고 인증서가 준비되면 **Enforce HTTPS**를 켭니다.
   루트 `CNAME`도 같은 도메인으로 설정되어 있으며 배포 산출물에 포함됩니다.
6. **Actions → Update and deploy Pages → Run workflow**에서 `sync`를 체크하여 실행합니다.
7. 성공 후 `status.json`의 `source.provider`가 `한국천문연구원`인지 확인합니다.

GitHub CLI를 사용하는 경우 다음 명령의 비공개 입력 프롬프트로 키를 등록할 수도 있습니다.

```sh
gh secret set DATA_GO_KR_SERVICE_KEY --repo hegelty/holidays-kr
```

키는 수집 단계에만 환경 변수로 전달됩니다. API 요청 URL이나 원본 응답을 로그에 출력하지 않습니다.
빌드·배포·PR 테스트에는 키를 전달하지 않으며 키 없이 실행할 수 있습니다.

키 등록 전에는 기존 스냅샷을 계속 제공합니다.
이때 `status.json`의 출처는 `legacy-snapshot`으로 표시됩니다.
API 호출 없이 첫 배포를 하려면 수동 실행 시 `sync`를 해제합니다.
키가 없는 상태에서 예약 갱신이나 `sync=true`를 실행하면 명확한 오류로 실패하고 기존 배포를 유지합니다.

## 제공 주소

- 사이트: `https://holidays.hegelty.me/`
- 전체 공휴일: `https://holidays.hegelty.me/basic.json`
- 연도별 공휴일: `https://holidays.hegelty.me/2026.json`
- 캘린더 구독: `https://holidays.hegelty.me/basic.ics`
- 연도별 다운로드: `2026.csv`, `2026.ics`
- 기념일: `anniversaries/` 아래 같은 파일 구조
- 상태: `https://holidays.hegelty.me/status.json`

전체 JSON은 `{ "2026": { "2026-01-01": ["1월1일"] }, ... }` 구조입니다.
연도별 JSON은 `{ "2026-01-01": ["1월1일"], ... }` 구조입니다.
날짜가 겹치면 명칭 배열에 여러 항목이 포함됩니다.
캘린더 구독 주소는 기존과 동일하며, 기념일은 공휴일과 별도로 제공합니다.

## 수집 범위와 실패 처리

매일 KST 06:23에 수집을 시도합니다. 예약 실행은 지연될 수 있습니다.

- HTTPS로 `SpcdeInfoService/getRestDeInfo`와 `getAnniversaryInfo`를 호출합니다.
- 기존에 지원하는 **모든 연도**와 한국 시간 기준 **올해부터 3년 뒤까지**를 조회합니다.
  예를 들어 2026년에는 2026~2029년을 시도합니다. 새 미래 연도는 API에 게시된 경우에만 제공됩니다.
  과거 데이터도 API에서 다시 수집하므로 원본 저장소의 과거 데이터를 계속 복사하지 않습니다.
- 연도별 조회에서 `pageNo`, `numOfRows`, `totalCount`를 확인하고 모든 페이지를 수집합니다.
- 공휴일은 `isHoliday=Y`인 항목만 반영하며, 기념일은 휴일 여부와 관계없이 반영합니다.
- 명칭은 API 응답을 사용합니다. 원본의 법률 기준 표기로 변환하거나 날짜를 추정하지 않습니다.
  최초 전환 시 이름·표기·지원 항목이 달라질 수 있고, 명칭이 바뀌면 해당 ICS 이벤트 UID도 달라집니다.
- 기존 연도 또는 올해가 비어 있거나, 인증 오류·누락 페이지·중복 레코드·잘못된 날짜가 발견되면 실패합니다.
- 아직 한 번도 제공하지 않은 새 미래 연도가 빈 응답이면 그 연도만 건너뜁니다.
  이미 제공 중인 미래 연도가 빈 응답이면 삭제하거나 조용히 유지하지 않고 갱신 전체를 실패시킵니다.
- 네트워크 오류 및 HTTP 429·일부 5xx 오류는 최대 3회 시도합니다.
  API가 HTTP 200으로 반환하는 인증·업무 오류도 실패로 처리합니다.
- XML 외부 엔티티 선언과 과도한 응답 크기를 거부하고 리다이렉트로 키가 전송되지 않게 합니다.

전체 수집 성공 후에만 `.data-update/`에 임시 데이터를 씁니다.
그다음 Node.js가 데이터와 출처를 다시 검증하여 `public/`과 `src` 프리셋을 갱신합니다.
`public/source.json`에는 공급 기관·서비스·조회 연도만 저장하며 키를 포함하지 않습니다.
내용이 같으면 커밋하지 않고, 최초 API 수집은 내용이 같더라도 출처 전환을 기록합니다.

`status.json`에는 데이터 커밋 시각, 지원 연도, 내용 SHA-256 및 출처가 포함됩니다.
성공 확인 시각을 매번 커밋하지 않으므로 **갱신 시각은 마지막 변경 시각이지 마지막 API 호출 시각이 아닙니다.**
마지막 수집 시도와 성공 여부는 Actions 실행 기록을 확인합니다.

수집·검증·빌드·push가 실패하면 배포하지 않습니다.
봇 커밋이 새 push 워크플로를 실행한다고 가정하지 않고 같은 실행에서 변경된 `main`을 다시 빌드합니다.
브랜치 보호가 봇의 직접 push를 금지하면 정책에 맞는 PR 기반 갱신으로 변경해야 합니다.
예약 실행과 실패 알림도 주기적으로 확인하세요.

## 로컬 실행

Node.js 22 이상, Python 3, Git을 사용합니다. npm·pip 패키지 설치는 필요 없습니다.

```sh
# 키 없이 테스트·오프라인 빌드
node --test scripts/pages.test.mjs
python3 -m unittest discover -s scripts -p 'test_*.py'
node scripts/pages.mjs build
```

출력 디렉터리 `_site/`는 다른 정적 웹 서버에도 배포할 수 있습니다.

실제 API 수집은 Bash에서 키를 화면·셸 기록에 남기지 않고 입력한 뒤 실행합니다.

```bash
read -rsp '공공데이터 API 키: ' DATA_GO_KR_SERVICE_KEY; echo
export DATA_GO_KR_SERVICE_KEY
python3 scripts/fetch_public_data.py && node scripts/pages.mjs import .data-update
unset DATA_GO_KR_SERVICE_KEY
```

수집 결과를 검토하고 `public/`과 `src`의 변경사항을 커밋한 뒤 빌드하세요.
배포용 ICS 시각은 `public/`의 마지막 커밋 시각을 사용합니다.
`.env`를 자동으로 읽지는 않으며, 키가 든 파일과 임시 수집 디렉터리는 커밋하지 않습니다.

직접 수정한 데이터는 다음 API 수집 때 덮어씁니다. 별도 수동 보정 규칙은 제공하지 않습니다.
형식 검증은 법적 정확성이나 공급 기관의 공휴일 반영 속도를 보증하지 않습니다.

## 원본 코드와 라이선스

기존 npm 패키지 개발 도구는 남겨 두었지만 Pages에는 사용하지 않습니다.
포크에서는 원본 npm 패키지로 게시하는 작업을 건너뜁니다.
기존 패키지 생성용 검증도 외부 데이터 저장소를 호출하지 않는 로컬 검증으로 변경했습니다.
원저작자의 MIT 라이선스를 유지합니다.
원본 사용법은 [원본 README](https://github.com/hyunbinseo/holidays-kr#readme)를 참고하세요.
