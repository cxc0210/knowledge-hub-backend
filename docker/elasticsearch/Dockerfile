ARG ELASTIC_VERSION=9.5.6

FROM docker.elastic.co/elasticsearch/elasticsearch:${ELASTIC_VERSION}

ARG IK_VERSION=9.5.6

RUN bin/elasticsearch-plugin install --batch \
    "https://get.infini.cloud/elasticsearch/analysis-ik/${IK_VERSION}"
