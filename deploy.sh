#!/bin/sh

echo ""
DEPLOY_BRANCH=`git rev-parse --abbrev-ref HEAD`

if [ `git rev-parse --verify origin/$DEPLOY_BRANCH` != `git rev-parse --verify $DEPLOY_BRANCH` ]; then
	echo "You have commits on the $DEPLOY_BRANCH branch not pushed to origin yet. They would not be deployed."
	echo "do you still which to deploy what's already in the repo? then type yes"
	read -p "" input
	if [ "x$input" != "xyes" ]; then
		exit 2
	fi
	echo ""
fi


host=data.c3voc.de

echo "deploying to $host
"

ssh voc@$host sh  << EOT
cd schedule
git pull
./test.sh

EOT