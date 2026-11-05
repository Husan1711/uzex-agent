FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python -m uzex_agent.prepare && rm data/uzex_spot_data.zip
ENV PORT=8000
EXPOSE 8000
CMD ["sh","-c","streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port ${PORT}"]
