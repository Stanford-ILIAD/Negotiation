#!/usr/bin/env bash
conda create -n craigslist python=2.7 --yes
source activate craigslist
pip install -r requirements.txt
conda install -c pytorch pytorch=0.4.1 --yes
conda install numpy=1.13.3 pandas=0.20.3 --yes
pip install torchtext==0.2.1
python -m nltk.downloader punkt
python -m nltk.downloader stopwords
python setup.py develop

cd craigslistbargain

# Download the training and validation sets
curl https://worksheets.codalab.org/rest/bundles/0xda2bae7241044dbaa4e8ebb02c280d8f/contents/blob/ > data/train.json
curl https://worksheets.codalab.org/rest/bundles/0xb0fe71ca124e43f6a783324734918d2c/contents/blob/ > data/dev.json

PYTHONPATH=. python core/price_tracker.py --train-examples-path data/train.json --output price_tracker.pkl

PYTHONPATH=. python parse_dialogue.py --transcripts data/train.json --price-tracker price_tracker.pkl --max-examples -1 --templates-output templates.pkl --model-output model.pkl --transcripts-output data/train-parsed.json
PYTHONPATH=. python parse_dialogue.py --transcripts data/dev.json --price-tracker price_tracker.pkl --max-examples -1 --templates-output templates.pkl --model-output model.pkl --transcripts-output data/dev-parsed.json

mkdir -p mappings/lf2lf;
mkdir -p cache/lf2lf;
mkdir -p checkpoint/lf2lf;
# Copy of the script in the README, but the gpuid field has been omitted so that it can run on a local machine
PYTHONPATH=. python main.py --schema-path data/craigslist-schema.json --train-examples-paths data/train-parsed.json --test-examples-paths data/dev-parsed.json \
--price-tracker price_tracker.pkl \
--model lf2lf \
--model-path checkpoint/lf2lf --mappings mappings/lf2lf \
--word-vec-size 300 --pretrained-wordvec '' '' \
--rnn-size 300 --rnn-type LSTM --global-attention multibank_general \
--num-context 2 --stateful \
--batch-size 128 --optim adagrad --learning-rate 0.01 \
--epochs 15 --report-every 500 \
--cache cache/lf2lf --ignore-cache \
--verbose