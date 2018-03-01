FROM python:alpine3.6

RUN apk add --no-cache bash

COPY requirements.txt /tmp/
RUN pip install --requirement /tmp/requirements.txt

ADD harness.py /
ADD VERSION /HARNESS_VERSION

ENTRYPOINT ["/harness.py"]
CMD ["/validator"]
