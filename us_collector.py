import os
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
    infinite_file = 'us_infinite.csv'
    recent_file = 'us_20days.csv'

    try:
        # 야후 파이낸스 스크리너 API 엔드포인트 (대형주 상위 100개 조회)
        api_url = "https://query2.finance.yahoo.com/v1/finance/screener"
        
        # API 요청 페이로드 (대형주 프리셋 활용)
        payload = {
            "size": 25,
            "offset": 0,
            "sortField": "intradaymarketcap",
            "sortType": "DESC",
            "quoteType": "EQUITY",
            "query": {
                "operator": "AND",
                "operands": [
                    {"operator": "eq", "operands": ["region", "us"]},
                    {"operator": "gt", "operands": ["intradaymarketcap", 10000000000]}
                ]
            }
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Content-Type": "application/json"
        }

        response = requests.post(api_url, json=payload, headers=headers)
        if response.status_code != 200:
            raise Exception(f"야후 API 접속 실패 (Status Code: {response.status_code})")

        data = response.json()
        quotes = data.get('finance', {}).get('result', [{}])[0].get('quotes', [])
        
        if not quotes:
            raise Exception("API에서 주식 데이터를 받아오지 못했습니다.")

        parsed_data = []
        for q in quotes:
            symbol = q.get('symbol', 'N/A')
            name = q.get('shortName', q.get('longName', 'N/A'))
            price = q.get('regularMarketPrice', 0.0)
            change_percent = q.get('regularMarketChangePercent', 0.0)
            
            parsed_data.append({
                'Symbol': symbol,
                'Name': name,
                'Price (Intraday)': price,
                '% Change': f"{change_percent:.2f}%",
                'Raw_Change': change_percent,
                'Date': today_str
            })

        df = pd.DataFrame(parsed_data)

        # 음수면 50 -> -25점 (2로 나누고 뺌) 처리
        df['Final_Score'] = df['Raw_Change'].apply(lambda x: -(50/2) if x < 0 else 50)
        df.drop(columns=['Raw_Change'], inplace=True)

        # 1. [무한 데이터] 저장 (계속 누적)
        if os.path.exists(infinite_file):
            inf_df = pd.read_csv(infinite_file)
            inf_df = pd.concat([inf_df, df])
        else:
            inf_df = df
        inf_df.to_csv(infinite_file, index=False)

        # 2. [20일 데이터] 저장 (최근 20일치 날짜만 유지)
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

        # 3. [나에게] 고급 정보 메시지 생성 및 전송
        advanced_info = f"📊 [US 대형주 고급 분석 - {today_str}]\n\n"
        for _, row in df.iterrows():
            advanced_info += f"[{row['Symbol']}] {row['Name']}\n현재가: {row['Price (Intraday)']} | 등락률: {row['% Change']}\n💡 점수: {row['Final_Score']}점\n\n"
        await bot.send_message(chat_id=my_chat_id, text=advanced_info)

        # 4. [친구에게] 채널용 일반 정보 메시지 생성 및 전송
        channel_info = f"📈 [R2D2 추천 미국 주식 - {today_str}]\n\n"
        good_stocks = df[df['Final_Score'] > 0]
        for _, row in good_stocks.iterrows():
            channel_info += f"• {row['Symbol']} ({row['Name']}) : {row['Price (Intraday)']}\n"
        if channel_chat_id:
            await bot.send_message(chat_id=channel_chat_id, text=channel_info)

    except Exception as e:
        error_msg = f"⚠️ 미국 주식 수집 중 에러 발생: {e}"
        print(error_msg)
        try:
            await bot.send_message(chat_id=my_chat_id, text=error_msg)
        except:
            pass

        if not os.path.exists(infinite_file):
            pd.DataFrame(columns=['Symbol', 'Name', 'Price (Intraday)', '% Change', 'Date', 'Final_Score']).to_csv(infinite_file, index=False)
        if not os.path.exists(recent_file):
            pd.DataFrame(columns=['Symbol', 'Name', 'Price (Intraday)', '% Change', 'Date', 'Final_Score']).to_csv(recent_file, index=False)

if __name__ == "__main__":
    asyncio.run(main())
