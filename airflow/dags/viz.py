import json
import pytz
import requests
import logging
import boto3

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go

from plotly.subplots import make_subplots
from pytz import timezone
from botocore.exceptions import ClientError
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
TODAY = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(timezone('US/Eastern'))
YESTERDAY = (TODAY - timedelta(days=1)).strftime('%Y-%m-%d')
TODAY = TODAY.strftime('%Y-%m-%d')

def get_relevant_articles(user_input, limit=5, certainity=0.5):
    try:
        s3_client = boto3.client('s3')
        s3_json_data = s3_client.get_object(Bucket='myairflowbuck', Key=f"news_summary_{user_input}_{TODAY}.json")['Body'].read().decode('utf-8')

        logger.info(f"Fetch {s3_json_data} from s3 success!!")
    except ClientError as e:
        logger.error(f"Exception {e} while fetching from s3")
        return None
    
    articles = []
    count_art = 0
    s3_json_data = json.loads(s3_json_data)
    for article in s3_json_data:
        if article['sentiment'] >= certainity:
            articles.append(article)
            count_art += 1
        if count_art == limit:
            break

    return articles

def get_ticker(company_name):
    url = "https://query2.finance.yahoo.com/v1/finance/search"
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    params = {'q':company_name, 'quotesCount':'1', 'newsCount':'0', 'region':'US'}
    headers = {'User-agent': user_agent}
    try:    
        response = requests.get(url, params=params, headers=headers).json()
        return response['quotes'][0]['symbol']
    except Exception as e:
        logger.error(f"Could not find ticker. Error {e}")
        return None    

def plot_stock_prices(user_input, article_data):

    ticker = get_ticker(user_input)
    if ticker is None:
        return

    stock_data = yf.download(ticker, YESTERDAY, TODAY, interval='1h')

    fig = make_subplots(rows=2, cols=1, shared_yaxes=True, vertical_spacing=0.2)

    fig.add_trace(go.Scatter(x=stock_data.index, y=stock_data['Open'], name='Open'), row=1, col=1)
    fig.add_trace(go.Scatter(x=stock_data.index, y=stock_data['Close'], name='Close'), row=1, col=1)

    fig.add_trace(go.Scatter(x=article_data['publishedAt'], y=article_data['sentiment'], name='sentiment'), row=2, col=1)
    
    fig.update_traces(textposition='top center')
    fig.update_xaxes(title_text='Datetime', row=1, col=1)
    fig.update_xaxes(title_text='Datetime', row=2, col=1)
    fig.update_yaxes(title_text='USD ($)', row=1, col=1)
    fig.update_yaxes(title_text='Sentiment', row=2, col=1)
    fig.update_layout(title_text=f"{ticker} stock prices and news sentiment")

    st.plotly_chart(fig, use_container_width=True)

    return stock_data

def plot_certainty_meter(stock, sentiment):
    diff = len(stock) - len(sentiment)

    if diff > 0:
        stock = stock[:-diff]
    elif diff < 0:
        sentiment = sentiment[:diff]

    covariance = np.cov(stock, sentiment)[0, 1]

    logger.info(f"Covariance is {covariance}")

    gauge(covariance,
          0,
          gTitle='Certainty Meter',
          gMode='gauge+number+delta'
        )

def gauge(gVal, gcDelta, gTitle, gMode, arTop=1, gcLow='#FF1708', gcMid='#FF9400', 
          gcHigh='#1B8720'):
    
    gaugeVal = round((gVal * 100), 1)
    top_axis_range = (arTop * 100)
    bottom_axis_range = -top_axis_range

    x1, x2, y1, y2 = .50, .50, .50, 1

    if gaugeVal <= bottom_axis_range/2: 
        gaugeColor = gcLow
    elif bottom_axis_range/2 < gaugeVal < top_axis_range/2:
        gaugeColor = gcMid
    else:
        gaugeColor = gcHigh

    fig1 = go.Figure(go.Indicator(
        mode = gMode,
        value = gaugeVal,
        domain = {'x': [x1, x2], 'y': [y1, y2]},
        delta={'reference': gcDelta, 'increasing':{'color': 'green'}, 'decreasing':{'color':'red'}, 'suffix':'%'},
        number = {"suffix": '%'},
        title = {'text': gTitle},
        gauge = {
            'axis': {'range': [bottom_axis_range, top_axis_range]},
            'bar' : {'color': gaugeColor}
        }
    ))

    config = {'displayModeBar': False}
    fig1.update_traces(title_font_color='white', selector=dict(type='indicator'))
    fig1.update_traces(number_font_color='rgb(14,17,23)', selector=dict(type='indicator'))
    fig1.update_traces(gauge_axis_tickfont_color='white', selector=dict(type='indicator'))
    fig1.update_layout(margin_b=5)
    fig1.update_layout(margin_l=20)
    fig1.update_layout(margin_r=20)
    fig1.update_layout(margin_t=50)

    fig1.update_layout(margin_autoexpand=True)

    st.plotly_chart(
        fig1, 
        use_container_width=True, 
        **{'config':config}
    )

st.title("Last night in the finance world.....")

st.header("Search")

user_input = st.text_input("Which ticker do you want to know about?")

limit = st.slider("Retrieve X most relevant articles:", 1, 20, 5)
certainty = st.slider("Certainty threshold for the relevancy", 0.0, 1.0, 0.5)

if st.button("Search"):
    st.header("Answer")
    with st.spinner(text="Thinking... :thinking_face:"):
        articles = get_relevant_articles(user_input=user_input.title(), limit=limit, certainity=certainty)
    
    if articles:
        st.success("Done! :smile:")

        st.header("Sources")

        for article in articles:
            st.write(f"Title: {article['title']}".replace("\n", " "))
            st.write(article["summary"])
            st.write(f"-{article['author']}")
            st.write("---")

        article_df = pd.DataFrame(articles)
        article_df['publishedAt'] = pd.to_datetime(article_df['publishedAt'])
        article_df.sort_values(by='publishedAt', inplace=True)

        stock_prices = plot_stock_prices(user_input, article_df)

        plot_certainty_meter(stock_prices['Close'].values, article_df['sentiment'].values)
    else:
        st.error("Failed! :rage:")