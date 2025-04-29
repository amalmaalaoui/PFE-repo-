pipeline {
    agent any

    environment {
        // Define any environment variables if needed
        IMAGE_NAME = 'qtpmigratorpfe-app'
        IMAGE_TAG = 'latest'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Setup Python Environment') {
            steps {
                script {
                    // Use Python 3.12 docker image for environment
                    docker.image('python:3.12-slim').inside {
                        sh '''
                        python -m pip install --upgrade pip setuptools wheel
                        pip install -r requirements.txt
                        '''
                    }
                }
            }
        }

        stage('Run Tests') {
            steps {
                script {
                    docker.image('python:3.12-slim').inside {
                        sh 'pytest tests'
                    }
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    docker.build("${env.IMAGE_NAME}:${env.IMAGE_TAG}")
                }
            }
        }

        // Optional: Add push or deploy stages here if needed
    }

    post {
        always {
            echo 'Cleaning up...'
            cleanWs()
        }
        success {
            echo 'Pipeline completed successfully.'
        }
        failure {
            echo 'Pipeline failed.'
        }
    }
}
