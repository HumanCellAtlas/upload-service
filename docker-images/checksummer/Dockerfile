FROM python:alpine3.6

RUN apk add --no-cache bash

COPY vendor.in /tmp/
COPY requirements.txt /tmp/
RUN pip install /tmp/crcmod==1.7/crcmod-1.7-cp36-cp36m-linux_x86_64.whl
RUN pip install --requirement /tmp/requirements.txt

ADD code /
RUN chmod +x /checksummer.py

CMD ["/checksummer.py"]
