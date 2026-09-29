# 대한민국의 공휴일

대한민국의 공휴일과 기념일을 `JSON`, `CSV`, `ICS` 파일로 제공합니다.
기념일은 공휴일과 별도입니다.

## 제공 파일

| 공휴일 | 기념일 | 내용 |
| --- | --- | --- |
| [basic.json](https://holidays.hegelty.me/basic.json) | [anniversaries/basic.json](https://holidays.hegelty.me/anniversaries/basic.json) | 전체 지원 연도의 날짜와 명칭 |
| [2026.json](https://holidays.hegelty.me/2026.json) | [anniversaries/2026.json](https://holidays.hegelty.me/anniversaries/2026.json) | 연도별 날짜와 명칭 |
| [2026.csv](https://holidays.hegelty.me/2026.csv) | [anniversaries/2026.csv](https://holidays.hegelty.me/anniversaries/2026.csv) | 연도별 CSV |
| [basic.ics](https://holidays.hegelty.me/basic.ics) | [anniversaries/basic.ics](https://holidays.hegelty.me/anniversaries/basic.ics) | 전체 지원 연도의 캘린더 구독 |
| [2026.ics](https://holidays.hegelty.me/2026.ics) | [anniversaries/2026.ics](https://holidays.hegelty.me/anniversaries/2026.ics) | 연도별 캘린더 |

연도별 파일은 `2026`을 원하는 연도로 바꾸어 사용합니다.
지원 연도는 [상태 파일](https://holidays.hegelty.me/status.json)에서 확인할 수 있습니다.
아직 발표되지 않은 미래 연도의 파일은 제공되지 않을 수 있습니다.

## JSON 사용법

```js
const response = await fetch('https://holidays.hegelty.me/2026.json');
if (!response.ok) throw new Error(`HTTP ${response.status}`);

const holidays = await response.json();
const names = holidays['2026-01-01'] ?? null; // ['1월1일']
const isHoliday = names !== null; // true
```

연도별 JSON은 `YYYY-MM-DD` 날짜를 키로, 공휴일 명칭 **배열**을 값으로 갖습니다.
같은 날짜에 여러 명칭이 있을 수 있습니다. `basic.json`은 연도를 한 번 더 묶은 형태입니다.

```json
{
	"2026-01-01": ["1월1일"],
	"2026-03-01": ["삼일절"]
}
```

위 JSON은 일부 날짜를 보여 주는 예시입니다.
이 데이터는 공휴일 여부를 나타내며, 모든 토요일·일요일을 휴일로 판별하는 용도는 아닙니다.

## 캘린더 구독

캘린더 앱의 URL 구독 기능에 [공휴일 캘린더](https://holidays.hegelty.me/basic.ics)
또는 [기념일 캘린더](https://holidays.hegelty.me/anniversaries/basic.ics) 주소를 등록합니다.

## 안내

- [배포·갱신·로컬 실행 가이드](./FORK.md)
- [원본 프로젝트 README](https://github.com/hyunbinseo/holidays-kr#readme)
- [MIT 라이선스](./LICENSE)
