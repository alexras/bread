version=$1
git_tag="v${version}"

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <version number>"
    exit 2
fi

if [[ ${version} =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]
then
  echo "Version format is valid"
else
  echo "Version format invalid; must be of the form 'MAJOR.MINOR.PATCH'"
  exit 1
fi


# Set version and build to version
sed -i .bak -e "s/version = '.*'/version = '${version}'/g" docs/source/conf.py
sed -i .bak -e "s/release = '.*'/release = '${version}'/g" docs/source/conf.py

# Replace version in __init__.py
sed -i .bak -e "s/__version__ = '.*'/__version__ = '${version}'/g" bread/__init__.py
sed -i .bak -e "s/version='.*'/version='${version}'/g" setup.py

# Remove backup files
find . -name "*.bak" -exec rm {} \;

# Tag revision as this version in git
git commit -a -m "Bumping version to ${git_tag}"
