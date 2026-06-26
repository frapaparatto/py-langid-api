# save as predict.sh, then: bash predict.sh "your text here"
curl --json "{\"text\": \"$1\"}" http://localhost:8000/identify-language
