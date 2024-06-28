import os
import json
import pytz
import logging
import boto3

from botocore.exceptions import ClientError
from pytz import timezone
from datetime import datetime, timedelta
from scraping_tools import get_everything
from viz import get_ticker

from airflow.decorators import task
from airflow.models.dag import DAG
from airflow.models.param import Param, ParamsDict
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import google.generativeai as genai


TODAY = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(timezone('US/Eastern'))
YESTERDAY = (TODAY - timedelta(days=1)).strftime('%Y-%m-%d')
TODAY = TODAY.strftime('%Y-%m-%d')

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get('GOOGLE_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')
analyzer = SentimentIntensityAnalyzer()

with DAG(
    'news_summarization',
    default_args={'retires':2},
    start_date=datetime(2024, 6, 4),
    schedule_interval=None,
    catchup=False,
    tags=['ui'],
    params={
        "tickers": Param(
            "Nvidia",
            type="string",
            title="Ticker to follow",
            description="Enter the name of the company to fetch news and analyze the sentiment and stock values",
            examples=(
                "Nvidia,Apple,Microsoft,Spotify,Crowdstrike,Dell,Adobe,Tesla,Mastercard,"
                "Visa,Netflix,Walmart,Amazon"
            ).split(","),
        ),
        "numberOfArticles": Param(
            10,
            type="number",
            title="Number of Articles",
            description="Enter number of articles to fetch",
            minimum=5,
            maximum=20
        )
    }
) as dag:
    
    @task(task_display_name="Extract and summarize news")
    def extract_and_summarize(**kwargs):
        """
        Extract and summarizes new for a ticker
        """
        params: ParamsDict = kwargs['params']
        company = params['tickers']
        ticker = get_ticker(company)
        num_articles = params['numberOfArticles']
        
        websites_to_scrape = [
            {'url':'https://finance.yahoo.com/topic/latest-news/', 'max_depth':1},
            {'url':f'https://www.google.com/finance/quote/{ticker}:NASDAQ', 'max_depth':0}
        ]
        
        all_articles = get_everything(webpages=websites_to_scrape,
                                      company=company.lower(),
                                    )
        
        summarized_news = []
        for article in all_articles:
            text = article['content']
            if text:
                summary = model.generate_content(f""" 
                Condense the following news article into a brief summary that highlights the
                main topic, keys events or findings, and any significant implications or
                outcomes. Avoid introductory phrases or any subjective language/interpretations
                and directly present the information.
                
                News Article:
                {text}
                
                """).text
                sentiment = analyzer.polarity_scores(summary)['compound']
                summarized_news.append({
                    'author':article['author'],
                    'title':article['title'],
                    'ticker':ticker,
                    'summary':summary.replace('$','\$'),
                    'sentiment':sentiment,
                    'publishedAt':article['publishedAt']
                })

        summarized_news = sorted(summarized_news, key=lambda x: x['sentiment'], reverse=True)

        if num_articles < len(summarized_news):
            summarized_news = summarized_news[:num_articles]

        try:
            outfile_name = f"news_summary_{company}_{TODAY}.json"

            with open(outfile_name, 'w') as outfile:
                json.dump(summarized_news, outfile)

            logger.info(f"Pushed to {outfile_name} to xcom")
            return outfile_name
        except Exception as e:
            logger.error(f"Exception {e} occured while pushing to xcom")
            return ""

    def s3_upload_file(**kwargs):
        bucket_name = kwargs['bucketName']

        file_name = kwargs['outfile']
        object_name = os.path.basename(file_name)

        try:
            s3_client = boto3.client('s3')
            response = s3_client.upload_file(file_name, bucket_name, object_name)
        except ClientError as e:
            logger.error(f"Exception {e} occured while s3 upload")
            return False
        
        return True
    
    s3_upload_json_file_task = PythonOperator(
        task_id='save_to_s3',
        python_callable=s3_upload_file,
        op_kwargs={'bucketName':'myairflowbuck', 'outfile':extract_and_summarize()}
    )

    viz_task = BashOperator(
        task_id='visualize_data',
        bash_command='streamlit run /opt/airflow/dags/viz.py',
        dag=dag,
    )

s3_upload_json_file_task >> viz_task