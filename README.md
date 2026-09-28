# 대한민국의 공휴일 · 독립 호스팅

[![데이터 갱신 및 배포](https://github.com/hegelty/holidays-kr/actions/workflows/pages.yml/badge.svg?branch=main)](https://github.com/hegelty/holidays-kr/actions/workflows/pages.yml)
[![서비스](./.github/badges/website.svg)](https://holidays.hegelty.me/)
[![MIT 라이선스](./.github/badges/license.svg)](./LICENSE)

대한민국의 공휴일과 기념일 데이터를 **JSON · CSV · ICS**로 제공하는 포크입니다.
GitHub Actions가 공공데이터포털의 **한국천문연구원 특일 정보 API**를 직접 호출해 갱신하고,
GitHub Pages에서 배포합니다. 원본 프로젝트의 데이터 저장소를 동기화하지 않습니다.

**[서비스 바로가기](https://holidays.hegelty.me/)** ·
**[캘린더 구독](https://holidays.hegelty.me/basic.ics)** ·
**[데이터 상태](https://holidays.hegelty.me/status.json)** ·
**[최근 커밋](https://github.com/hegelty/holidays-kr/commits/main/)** ·
**[운영 안내](./FORK.md)**

## 주요 특징

- **자체 도메인**: 모든 데이터를 `holidays.hegelty.me`에서 제공합니다.
- **단순한 조회**: API 키, 회원가입, npm 패키지 설치 없이 정적 파일을 사용합니다.
- **조회 시 외부 서비스 호출 없음**: 원저자의 도메인이나 npm CDN에 접근하지 않습니다.
- **직접 수집**: 공휴일·기념일을 공공데이터 API에서 직접 가져옵니다.
- **자동 갱신**: 매일 한국 시간 06:23에 API를 조회하고, 변경된 경우에만 커밋합니다.
- **실패 시 기존 데이터 유지**: 갱신이나 검증에 실패하면 기존 배포를 유지합니다.
- **별도 패키지 설치 없는 빌드**: Node.js 기본 모듈과 저장소의 JSON만으로 사이트를 생성합니다.

## 데이터 주소

| 용도 | 주소 |
| --- | --- |
| 전체 연도 공휴일 JSON | [basic.json](https://holidays.hegelty.me/basic.json) |
| 연도별 공휴일 JSON | [2026.json](https://holidays.hegelty.me/2026.json) |
| 전체 연도 공휴일 캘린더 | [basic.ics](https://holidays.hegelty.me/basic.ics) |
| 연도별 공휴일 캘린더 | [2026.ics](https://holidays.hegelty.me/2026.ics) |
| 연도별 공휴일 CSV | [2026.csv](https://holidays.hegelty.me/2026.csv) |
| 전체 연도 기념일 JSON | [anniversaries/basic.json](https://holidays.hegelty.me/anniversaries/basic.json) |
| 전체 연도 기념일 캘린더 | [anniversaries/basic.ics](https://holidays.hegelty.me/anniversaries/basic.ics) |
| 데이터 출처·갱신 시각·지원 연도·해시 | [status.json](https://holidays.hegelty.me/status.json) |

연도별 파일은 `2026`을 필요한 연도로 바꾸어 사용합니다.
기념일도 `anniversaries/2026.json`, `anniversaries/2026.csv`, `anniversaries/2026.ics` 형식으로 제공합니다.
지원하지 않는 연도의 파일은 HTTP 404를 반환하므로 응답 상태를 확인하세요.

**기념일은 공휴일과 별개입니다.** 휴일 조회에는 공휴일 데이터를 사용하세요.

## JSON 사용법

```js
const response = await fetch('https://holidays.hegelty.me/2026.json');
if (!response.ok) throw new Error(`공휴일 데이터 조회 실패: HTTP ${response.status}`);

const holidays = await response.json();

// 날짜는 한국 시간 기준 YYYY-MM-DD 문자열을 사용합니다.
const date = '2026-01-01';
const isHoliday = Object.hasOwn(holidays, date);
const holidayNames = holidays[date] ?? null;

console.log(isHoliday); // true
console.log(holidayNames); // ['1월 1일']
```

연도별 JSON은 날짜를 키로, 공휴일 명칭 배열을 값으로 갖습니다.
같은 날짜에 여러 공휴일이 겹칠 수 있으므로 명칭은 항상 배열입니다.

```json
{
	"2026-01-01": ["1월 1일"],
	"2026-03-01": ["3ㆍ1절"]
}
```

위 예시는 데이터의 일부입니다. 전체 연도 파일인 `basic.json`은
`{ "2026": { "2026-01-01": ["1월 1일"] }, ... }`처럼 연도별로 묶여 있습니다.

이 조회는 데이터에 등록된 공휴일 여부를 확인합니다. 단순한 토요일·일요일 판별과는 별개입니다.

## 캘린더 구독

캘린더 앱의 URL 구독 기능에 다음 주소를 등록합니다.

```text
https://holidays.hegelty.me/basic.ics
```

기념일을 별도 캘린더로 구독하려면 다음 주소를 사용합니다.

```text
https://holidays.hegelty.me/anniversaries/basic.ics
```

## 자동 갱신과 안정성

수집 출처는 [한국천문연구원 특일 정보 API](https://www.data.go.kr/data/15012690/openapi.do)입니다.

- 공휴일: `getRestDeInfo` 응답 중 `isHoliday=Y`인 항목
- 기념일: `getAnniversaryInfo` 응답
- 기존 지원 연도 전체와 한국 시간 기준 올해·내년을 조회하며 모든 페이지를 수집합니다.
- API 오류, 페이지 누락, 잘못된 날짜, 기존 연도의 빈 응답은 갱신 실패로 처리합니다.
- 아직 게시되지 않은 **새로운 미래 연도**만 건너뛰고, 나머지는 전부 성공해야 반영합니다.
- 명칭은 API 응답을 사용하므로 원본 프로젝트의 명칭과 다를 수 있습니다.

검증을 통과한 변경만 저장소에 커밋하고 같은 실행에서 빌드·배포합니다.
예약 실행은 지연될 수 있으며, 수동 실행도 가능합니다.

> 최초 API 갱신에 성공하기 전에는 기존 스냅샷을 제공합니다.
> `status.json`의 `source.provider`가 `legacy-snapshot`이면 아직 API 수집이 완료되지 않은 상태입니다.

**조회에는 API 키가 필요 없지만 수집에는 키가 필요합니다.**
원본 저장소에 대한 수급 의존성은 제거했으며, 공식 API와 GitHub Actions·Pages 의존성은 남아 있습니다.
공식 API 장애나 키 만료로 갱신에 실패해도 기존 배포는 유지됩니다.
형식 검증이 공휴일 정보의 정확성까지 보증하지는 않습니다.

### 수집 키 등록

특일 정보 API의 활용 신청 후 발급받은 키를 이 저장소의
**Settings → Secrets and variables → Actions → New repository secret**에 등록합니다.

```text
Name: DATA_GO_KR_SERVICE_KEY
Value: 공공데이터포털 인증키 (Encoding 또는 Decoding)
```

키는 수집 단계의 환경 변수로만 전달하며 코드·배포 파일·로그에 기록하지 않습니다.
등록 후 **Actions → Update and deploy Pages → Run workflow**에서 `sync`를 체크해 실행합니다.
키 없이 기존 데이터만 배포하려면 `sync`를 해제합니다.

상세 설정과 실패 처리 방법은 [포크 운영 안내](./FORK.md)를 참고하세요.

## 로컬 검증 및 빌드

Pages 빌드는 Node.js 22 이상과 Git만 필요합니다.
API 수집과 수집기 테스트에는 Python 3도 필요합니다.
`pnpm install`이나 `pip install`은 필요하지 않습니다.

```sh
node --test scripts/pages.test.mjs
python3 -m unittest discover -s scripts -p 'test_*.py'
node scripts/pages.mjs build
```

생성된 `_site/`를 정적 웹 서버에 배포할 수 있습니다.
도메인 설정은 루트의 `CNAME`, 자동화 설정은
[Pages 워크플로](./.github/workflows/pages.yml)에서 관리합니다.

## 원본 및 라이선스

- [원본 프로젝트 README](https://github.com/hyunbinseo/holidays-kr#readme)
- [MIT 라이선스](./LICENSE) — 원저작자의 저작권 고지를 유지합니다.
