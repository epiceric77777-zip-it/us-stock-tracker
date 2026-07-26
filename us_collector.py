import os
import io
import requests
import pandas as pd
import asyncio
from datetime import datetime
from telegram import Bot

async def main():
    bot_token = os.environ.get('TELEGRAM_TOKEN')
    my_chat_id = os.environ.get('MY_CHAT_ID')
    channel_chat_id = os.environ.get('CHANNEL_CHAT_ID') 
    bot = Bot(token=bot_token)

    today_str = datetime.now().strftime("%Y-%m-%d")
    url = "https://finance.yahoo.com/markets/stocks/large-cap-stocks/?start=0&count=100"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    infinite_file = 'us_infinite.csv'
    recent_file = 'us_20days.csv'

    try:
        # 1. 데이터 수집
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise Exception(f"야후 파이낸스 접속 실패 (Status Code: {response.status_code})")

        tables = pd.read_html(io.StringIO(response.text))
        if not tables:
            raise Exception("페이지에서 주식 테이블을 찾을 수 없습니다.")

        df = tables[0].head(15).copy()
        
        # 필수 컬럼 존재 확인 및 가공
        if 'Symbol' not in df.columns or '% Change' not in df.columns:
            raise Exception("필수 주식 데이터 컬럼이 존재하지 않습니다.")

        df['Date'] = today_str
        
        # % Change 파싱 안전 장치
        df['Change_Score'] = df['% Change'].astype(str).str.replace('%', '').str.replace('+', '').str.replace(',', '')
        df['Change_Score'] = pd.to_numeric(df['Change_Score'], errors='coerce').fillna(0)
        
        # 음수면 50 -> -25점 (2로 나누고 뺌) 처리
        df['Final_Score'] = df['Change_Score'].apply(lambda x: -(50/2) if x < 0 else 50)

        # 2. [무한 데이터] 저장 (계속 누적)
        if os.path.exists(infinite_file):
            inf_df = pd.read_csv(infinite_file)
            inf_df = pd.concat([inf_df, df])
        else:
            inf_df = df
        inf_df.to_csv(infinite_file, index=False)

        # 3. [20일 데이터] 저장 (최근 20일치 날짜만 유지)
        if os.path.exists(recent_file):
            df20 = pd.read_csv(recent_file)
            df20 = pd.concat([df20, df])
            unique_dates = df20['Date'].unique()
            if len(unique_dates) > 20:
                recent_dates = unique_dates[-20:]
                df20 = df20[df20['Date'].isin(recent_dates)]
        else:
            df20 = df
        df20.to_csv(recent_file, index=False)

        # 4. [나에게] 고급 정보 메시지 생성 및 전송
        advanced_info = f"📊 [US 대형주 고급 분석 - {today_str}]\n\n"
        for _, row in df.iterrows():
            advanced_info += f"[{row.get('Symbol', 'N/A')}] {row.get('Name', 'N/A')}\n현재가: {row.get('Price (Intraday)', 'N/A')} | 등락률: {row.get('% Change', 'N/A')}\n💡 점수: {row.get('Final_Score', 0)}점\n\n"
        await bot.send_message(chat_id=my_chat_id, text=advanced_info)

        # 5. [친구에게] 채널용 일반 정보 메시지 생성 및 전송
        channel_info = f"📈 [R2D2 추천 미국 주식 - {today_str}]\n\n"
        good_stocks = df[df['Final_Score'] > 0]
        for _, row in good_stocks.iterrows():
            channel_info += f"• {row.get('Symbol', 'N/A')} ({row.get('Name', 'N/A')}) : {row.get('Price (Intraday)', 'N/A')}\n"
        if channel_chat_id:
            await bot.send_message(chat_id=channel_chat_id, text=channel_info)

    except Exception as e:
        # 에러 발생 시 텔레그램으로 알림 발송
        error_msg = f"⚠️ 미국 주식 수집 중 에러 발생: {e}"
        print(error_msg)
        try:
            await bot.send_message(chat_id=my_chat_id, text=error_msg)
        except:
            pass

        # 에러가 나더라도 빈 CSV 파일이라도 생성해서 Git 커밋 에러(fatal: pathspec '*.csv' did not match)를 방지
        if not os.path.exists(infinite_file):
            pd.DataFrame(columns=['Symbol', 'Name', 'Price (Intraday)', '% Change', 'Date', 'Final_Score']).to_csv(infinite_file, index=False)
        if not os.path.exists(recent_file):
            pd.DataFrame(columns=['Symbol', 'Name', 'Price (Intraday)', '% Change', 'Date', 'Final_Score']).to_csv(recent_file, index=False)

if __name__ == "__main__":
    asyncio.run(main())
