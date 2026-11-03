---
type: brief
owner_agent: deck-marketer
status: draft
sources:
  - raw/decks/2026-11-03-1st-deck/project/slides/ (origin, case, problem, global, speed, quality, trust, whynow, demand, market, competition, positioning, engine, service, bizmodel, plan, closing)
  - raw/market/2026-11-03-market-brief.md
  - "claude.ai Project file: 262R 서울-대학원정보추출과텍스트마이닝 ... 수업 계획서.pdf (not yet in raw/)"
last_reviewed: 2026-11-03
---
# 2차 발표 브리프 (AAA639)

출처 표기: `[deck:<id>]` = `raw/decks/2026-11-03-1st-deck/project/slides/<id>.html`, `[brief]` = `raw/market/2026-11-03-market-brief.md`,
`[syllabus]` = 수업 계획서 PDF (claude.ai Project 파일, raw/에는 아직 없음). [확인 필요] = 사실이 아직 없음. 지어내지 않음.

## 0. 이 발표가 해야 하는 일
- **청중**: AAA639 수강생과 임희석 교수. 시간 약 10분 (task card).
- **수업이 2차에 요구하는 것**: 10주차 【2차 발표】 "디자인 & 서비스 개발". 그 사이 수업이 6주 AI 디자인 I 브랜딩 & UI, 7주 AI 디자인 II UI 고도화,
  8주 AI 코딩 I 개발 환경 & 백엔드, 9주 AI 코딩 II 서비스 통합 개발 [syllabus]. 그래서 2차는 01을 짧게(요약 + 검증 결과) 하고 02–04에 시간을 쓴다.
- **평가 비중**: 문제 정의 적절성 10%, AI 주도 해결 방법 설계·도출 30%, 보고서 10%, 발표 자료·구두 발표 50% [syllabus].
- **청중이 가지고 나가야 할 판단**: "1차에서 약속한 세 가지(Mac 앱 MVP, 커밋 113개 재현 정밀도, 인터뷰 12명)를 실제로 해 왔고,
  잘 안 된 부분도 숨기지 않았다. 3차에 시범 사용자 10명과 IR까지 갈 수 있겠다." 약속 출처: [deck:plan] 일정의 "2차" 행, [deck:closing] 노트.
- **기억할 한 가지**: 코드가 바뀌면, 논문의 어느 그림과 문장을 다시 봐야 하는지 앱이 먼저 알려 준다. 그리고 그 알림이 얼마나 맞는지 쟀다.

## 1. 페인 포인트
| 항목 | 내용 | 근거 |
| --- | --- | --- |
| 누가 | 코딩 에이전트와 함께 실험 코드를 짜고 LaTeX로 논문을 쓰는 ML 대학원생 | [deck:origin] (Juhyeong 본인, n=1) |
| 언제 (트리거) | 스크립트 하나를 고친 직후. 예: 9/17 `tau_trajectories.py` 수정 → 결과 CSV → Fig. 5–10 → RQ2, RQ3 결론 | [deck:problem] |
| 얼마나 자주 | 2주 동안 커밋 113개, 하루 평균 약 8번 | [deck:origin], [deck:problem] |
| 무엇을 잃나 | 옛 결과가 논문에 남음. 9/17 기준 다시 볼 산출물 79개. 초록 "311 series" vs README "231 scored series" (어느 쪽이 맞는지 미확인) | [deck:problem], [deck:case] |
| 지금 하는 방법 | 연구자의 기억. 연결이 어디에도 기록되지 않음. 몇 주 쉬면 그 기억도 흐려짐 | [deck:problem] 노트 |
| 왜 실패하나 | 코드는 GitHub, 결과는 서버, 원고는 Overleaf, 주의사항은 AI 대화 속. 속도가 사람 기억을 넘음 | [deck:origin], [deck:speed] |
| 다른 연구자도 그런가 | **아직 모름.** H1(옛 결과가 남은 적 있음 ≥ 50%), H2(기억·메모로 파악 ≥ 60%)를 설문 n ≥ 60, 인터뷰 12–15명으로 확인 예정 | [deck:plan] |

비용(시간)은 아직 숫자가 없다: [확인 필요: 인터뷰에서 들은 "다시 확인에 쓴 시간"]. 리젝트·평판 비용은 정책으로만 근거가 있다
(ICLR 2026 가짜 참고문헌 전부 데스크 리젝트, arXiv CS 1년 제출 금지 2026.5) [deck:demand], [brief §1]. 이건 참고문헌 쪽 근거이고 "옛 결과가 남는 문제"의 직접 비용은 아니다. 섞어 말하지 않는다.

## 2. 페르소나와 할 일 (JTBD)
- **P1 사용자: ML 대학원생 (석박사), 투고 준비 중.** 도구: GitHub, 연구 서버(GPU), Overleaf, Claude Code 같은 코딩 에이전트 [deck:origin].
  JTBD: "코드를 고쳤을 때, 논문에서 다시 봐야 할 그림과 문장만 바로 알고 싶다."
  인터뷰로 확인할 것: [확인 필요: 인터뷰 12명 중 이 페르소나에 맞는 사람 수, 쓰는 도구 분포].
- **P2 구매자: 연구실 PI.** 학생이 졸업해도 어떤 코드가 어떤 그림을 만들었는지 남는 것이 가치 [deck:bizmodel] 노트.
  연구실 좌석 연 300–600달러는 **추정** [deck:market], [brief §3]. [확인 필요: PI 인터뷰 여부, 지불 의사].
- 사용자 ≠ 구매자: 개인 저자는 PAT 같은 무료 도구 때문에 기대 가격이 0에 가까움 → 매출은 연구실 좌석부터 [deck:market], [brief §2, §3].

## 3. 창업자 이야기 (Juhyeong이 말한 것만)
2026년 9월, 시계열 이상탐지 평가 지표 논문(WWW 투고 준비)을 쓰면서 Claude Code 에이전트와 2주에 커밋 113개.
"논문의 어떤 그림이 최신 결과인지 저도 확실히 말할 수 없었습니다." 이전에 ACM Computing Surveys 서베이로 Major Revision(코퍼스 부족, 표기 오류) [deck:origin].
그리고 해법 구조는 본인 연구 주제인 이상탐지의 알람-분석기 구조에서 가져옴 [deck:concept] 노트.
2차에서는 이 이야기를 한 장(요약)으로 줄이고, "그 뒤 무엇을 만들었고 얼마나 맞았는지"로 넘어간다.

## 4. 왜 지금 (날짜가 있는 것만)
- 2025 → 2026: ICLR 11,600 → 19,525편, ICML 12,107 → 23,918편 [deck:whynow], [brief §1].
- 2026 상반기: Google PAT, STOC·ICML 저자에게 무료 (4,700편+). 2026.5 arXiv CS 1년 제출 금지 [deck:whynow], [brief §1–2].
- 2026 하반기: NeurIPS 2026 PAT 채택. ICLR 2027 초록 등록 60,000+는 **비공식 보도** [deck:whynow].
- 2차용 새 날짜: [확인 필요: 1차 이후 생긴 사건, 예: 다음 마감(ICML 2027 마감은 보통 1월 말, 확인 필요 [brief §8])].

## 5. 포지셔닝
- 한 줄: **"코드가 바뀌면 논문의 어느 줄을 다시 봐야 하는지 알려 주는, 연구용 CI"** [deck:positioning].
- 이기는 자리: (1) 시간축 변경 추적 (커밋, 실행, 원고 버전), (2) 모든 알림에 파일·줄·근거, (3) 원고가 PC 밖으로 안 나가는 구조 [deck:positioning], [deck:service].
- 지는 자리, 그리고 인정할 것: 참고문헌 실재 검사는 무료 도구가 이미 많음 (RefChecker, Bib Check Agent 등) [deck:competition], [brief §1b].
  Google PAT는 무료이고 학회가 배포 [brief §2]. 코드→결과 의존성은 DVC, showyourwork가 한다 (논문 문장까지는 안 잇는다는 건 **일반 지식 기준, 직접 확인 전**) [deck:competition].

## 6. 약점과 답 (슬라이드에서 말할 것)
| 약점 | 답 | 어디서 말하나 |
| --- | --- | --- |
| 정밀도를 **내 저장소 하나**로, **내가 붙인 정답**으로 쟀다 | 정답 기준을 미리 적어 두고, 다른 사람 1명이 일부를 따로 라벨링해 일치도 보고 [확인 필요: 실제로 했는지]. 두 번째 저장소 [확인 필요] | 14 replay, 15 misses |
| 인터뷰가 고려대 ML 중심, 설문은 자기선택 표본 | 표본 구성을 슬라이드에 그대로 표시. 해외 응답자 수 [확인 필요] | 5 validation |
| 저자가 내는 시장은 작다 (SAM 연 1,000만–2,000만 달러, **추정**) | 매출은 연구실 좌석, 오픈소스로 사용자 확보 [deck:market], [deck:bizmodel] | 19 next (짧게), Q&A |
| 무료 경쟁 (PAT, OSS 플러그인) | 원고 한 장 점검이 아니라 변경 추적. 측정한 정밀도를 공개 | 4 promises / Q&A |
| 10분에 20장 + 데모 | 데모는 60초 녹화 영상 [확인 필요], 01은 2분 안에 끝냄 | outline 시간표 |

## 7. 문서 간 충돌 (QA·CTO에게)
- `CLAUDE.md` Scope와 `wiki/vision/vision.md`는 아직 "제출 전 점검기(본문-부록 일치, 참고문헌)"를 말하고, 1차 덱은 "변경 추적"으로 바뀌었다.
  이 덱은 1차 덱(변경 추적)을 따른다. ADR로 정리할 필요 있음 (Juhyeong 승인 사항).
- 수업 계획서는 claude.ai Project에만 있고 `raw/`에 없다 (CLAUDE.md Layout은 raw/에 syllabus가 있다고 함).
