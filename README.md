# Uncharted Waters II for Web

<p align="center">
  <img src="./screenshot.png" alt="Uncharted Water Play" width="600" />
</p>

> [대항해시대 오리진](https://uwo.floor.line.games/kr/main) 2022년 8월 23일 정식 출시!

## 소개

대항해시대 오리진의 소식을 듣고 복습겸 대항해시대2를 플레이하려고 했습니다. 시간이 많이 흘러, 컴퓨터 환경이 많이 변하였습니다.
도스 환경을 구축하는 프로그램도 원활하게 동작하지 않고, 키보드는 텐키리스를 사용해서 항해할 때 조작도 복잡하였습니다.

저 같은 사람이 분명히 많을 거 같아 대항해시대2(한글판)를 웹에서 할 수 있도록 작업하였습니다.

## 사용법

- 공통
  - 게임내 저장파일은 브라우저 자체(IndexedDB)에 저장됩니다. 브라우저를 종료해도 저장파일이 계속 남아있습니다.
- 데스크탑 + 풀키보드 배열을 사용하는 경우
  - 오리지날 키매핑으로 게임 진행이 가능합니다.
- 데스크탑 + 텐키리스 배열을 사용하는 경우
  - 항해시 방향키를 사용할 수 있습니다.
  - `Q`, `W`, `E`, `R` 키를 이용하여 메뉴를 활성화 할 수 있습니다.
- 모바일의 경우
  - 가상 키패드를 활용해서 게임을 진행할 수 있습니다.

## 짱짱맨 버전

이 포크의 기본 커스텀 작업 대상은 짱짱맨 버전입니다. 기본판에서 시작한 이 버전의 게임 데이터는 `game/mod_jjangjjangman.zip`에서 수정합니다. 업데이트 후에도 기존 세이브를 이어 쓸 수 있도록 모드 ID `mod_jjangjjangman`을 유지합니다.

v1.1에서는 기존 130개 항구에 인천항·부산항·서울항을 더했습니다. 세 곳은 처음부터 위치를 아는 보급항입니다. 서울항은 서해에서 인천항 북쪽 하구로 들어가 한강을 동쪽으로 거슬러 올라가면 나옵니다. 부산항은 한반도 남동쪽 해안에 있습니다.

항구 좌표와 강 지형을 수정한 뒤 원본 한글판에서 짱짱맨 게임 파일을 다시 생성할 수 있습니다.

```sh
python3 tools/jjangjjangman/korea_ports.py game/water2.zip game/mod_jjangjjangman.zip
```

## 모드

- [교정버전 v1.08](https://cafe.naver.com/daehangs/73594)
- [에르네스트 모드 v1.11](https://cafe.naver.com/daehangs/71466)
- [정화편(기본판) v3.0](https://cafe.naver.com/daehangs/52187)
- [밀란다 / 살바도르편 20216.11.26](https://cafe.naver.com/daehangs/66350)

## 실행

**윈도우 익스플로러**는 지원하지 않습니다. 반드시 [크롬](https://www.google.com/chrome/)이나, [파이어폭스](https://www.mozilla.org/ko/firefox/new/),
또는, 모바일 브라우저에서 실행해주시기 바랍니다.

**[게임 시작하기](https://water2.dist.be)**

## 문의하기

게임 중 버그나 개선할 사항, 질문 등이 있다면 [이슈 페이지](https://github.com/wan2land/unchartedwater2/issues)에 작성해주세요. 시간 날 때 천천히 해결해놓겠습니다.
