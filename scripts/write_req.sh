# write the requirements file from pyproject.toml
# 
# to be used by pip like this:
# >> pip install -r examples/REQUIRES.txt

sed -n "/\^/ s///p" pyproject.toml| sed -e 's/=/==/' -e 's/\"//g' -e '/^python/ d' > examples/REQUIRES.txt

cat examples/REQUIRES.txt


