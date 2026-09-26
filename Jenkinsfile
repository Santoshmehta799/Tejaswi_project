pipeline {
    agent any

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Docker Build') {
            steps {
                sh 'docker build -t santu-backend:latest .'
            }
        }

        stage('Run Application') {
            steps {
                sh 'docker compose up -d'
            }
        }

        stage('Push to ECR') {
            steps {
                sh '''
                    aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 641628981724.dkr.ecr.us-east-1.amazonaws.com

                    docker tag santu-backend:latest 641628981724.dkr.ecr.us-east-1.amazonaws.com/santu-backend:latest

                    docker push 641628981724.dkr.ecr.us-east-1.amazonaws.com/santu-backend:latest
                '''
            }
        }
    }
}
