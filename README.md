# Stock Market News Analysis and Sentiment Prediction Web App

## Overview
This project is a web application designed to analyze market news and predict stock price movements, helping investors make informed decisions. The app is built using Airflow, Docker, and Streamlit, and is deployed on AWS EC2. It includes an ETL pipeline that scrapes, summarizes, and analyzes news sentiment, storing the results on S3.

## Features
- **ETL Pipeline:** Extracts, transforms and loads news data using Airflow.
- **News Summarization:** Utilizes the Gemini API with prompting to summarize news articles.
- **Sentiment Analysis:** Calculates the sentiment of the summarized news.
- **Certainty Score:** Developed a metric that combines previous day's stock prices with current news sentiment to produce a certainty score for investors.
- **Containerized Deployment:** Uses Docker for containerization and AWS EC2 for deployment.
- **User Interface:** Streamlit provides an interactive frontend for users.

## Technologies Used
- **Airflow:** For orchestrating the ETL pipeline.
- **Docker:** For containerizing the application.
- **Streamlit:** For the web app frontend.
- **AWS EC2:** For deploying the app.
- **Gemini API:** For news summarization.
- **S3:** For data storage.

## Architecture
1. **Data Extraction:** Scrapes the web for news articles related to the desired company using BeautifulSoup. Alternatively, use newsapi-python to fetch the latest news.
2. **Data Transformation:** Summarizes the news articles and calculates sentiment.
3. **Data Loading:** Stores the processed data on AWS S3.
4. **Metric Development:** Analyzes the previous day's stock prices against news sentiment to create a certainty score.
5. **Deployment:** Containerized using Docker and deployed on an AWS EC2 instance with a Streamlit frontend.

## Installation and Setup
1. **Spawn an EC2 instance on AWS**
   - Set up an EC2 instance (minimum t2-medium)
   - Create an S3
   - Create an IAM role and give full access to S3 and EC2
   - Assign IAM role to EC2 instance
   - Connect to EC2

2. **Clone the repository on your EC2 and install required packages:**
    ```bash
    git clone https://github.com/LucienCaslte/news-summarization-gemini
    pip install -r requirements.txt
    ```

3. **Build and run the Docker container:**
    - Build image
    ```bash
    cd airflow
    docker build -t stock-news-app .
    docker run -d -p 8080:8080 -p 8501:8501 stock-news-app
    ```
    - Check the docker containerId:
    ```bash
    docker ps
    docker exec -ti containerId /bin/bash
    ```
    - Retrieve airflow-pwd:
    ```bash
    cat standalone-airflow-password.txt
    ```
## Usage
1. Access the web app through the deployed EC2 instance's public IP address.
2. For airflow use the username "admin" and password you retrieved earlier and run the DAG.
3. Input the desired company's name and the number of news articles to fetch, wait till DAG runs successfully.
4. View the summarized news, sentiment analysis, and certainty score on Streamlit by refreshing the browser.

## Contributing
Contributions are welcome! Please fork the repository and submit a pull request.

## Contact
For any questions or inquiries, please contact [sumitpatil351@gmail.com](mailto:sumitpatil351@gmail.com).

---
