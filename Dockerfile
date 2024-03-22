# syntax=docker/dockerfile:1

FROM python:3.8-slim-buster

WORKDIR /app

COPY . .
#ADD ./* $HOME/src/


#RUN ls /app

RUN pip3 install -r requirements.txt

ENTRYPOINT ["bash","script.sh"]

#CMD ["python", "telegram_webhook.py"]

#CMD ["python", "telegram_bot_accelerator.py"]

#CMD ["tail", "-f", "/dev/null"]

