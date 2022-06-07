# install a ipython kernel in the local venv
#
# run this once, then use it like this:
# >> jupyter qtconsole --kernel=pytrms-test

poetry run python -m ipykernel install --user --name pytrms-test --display-name "Python (pytrms)"

