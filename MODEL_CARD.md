# lambda 1.0

An experimental English text model trained from random weights, without an
external pretrained language model or pretrained tokenizer.

| Property | Value |
| --- | --- |
| Model ID | `lambda-1.0` |
| Language | English |
| Architecture | Autoregressive MLP, embedding and two tanh hidden layers |
| Parameters | 747,008 |
| Vocabulary | 1,024 locally learned BPE tokens |
| Context | 64 tokens |
| Precision | float32 |
| Runtime | Local CPU / NumPy |
| Model file | `lambda_cli/assets/model.npz` |

The exact exported checkpoint step, file size and SHA-256 are recorded in
`lambda_cli/assets/model.json`. Only inference weights, vocabulary and
metadata are distributed; optimizer state is excluded.

## English training data

The English dataset contains **3,691 distinct examples and 470,801 characters**:
original definitions, short conversations, arithmetic examples, short-context
questions, descriptions and stories generated with explicit templates. These
are synthetic templates, not thousands of independent knowledge sources.

The dataset also uses public-domain prose from Lewis Carroll's *Alice's
Adventures in Wonderland* (1865), obtained from
[Project Gutenberg, ebook 11](https://www.gutenberg.org/ebooks/11).
Project Gutenberg identifies this text as public domain in the USA. Carroll
died in 1898. The Gutenberg header and footer were excluded from training.
The novel and full training dataset are not included in this application.

Whole examples are held out for validation. A general language stage is
followed by a dialogue stage that samples answer beginnings more often.
The distributed checkpoint is chosen using validation. Similar templates
can make validation optimistic; it is not a general reasoning benchmark.

## Limitations

The model may memorize examples, confuse concepts, make arithmetic errors
or generate nonsensical text. It is not a general-purpose assistant. It has
no internet access, live information, tools, or conversational memory.
Only the most recent 64 input tokens are used. The vocabulary does not
support every Unicode character. Unsupported characters are reported.

The million-token allowance is a usage policy, not a context length or a
claim about the model's knowledge. The terminal interface adds no learned
capabilities. Token probabilities do not measure factual reliability.
