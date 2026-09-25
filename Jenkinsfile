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
    }
}
