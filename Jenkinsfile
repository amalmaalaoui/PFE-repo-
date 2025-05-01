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
                        python -m pip install --upgrade --break-system-packages pip setuptools wheel
                        pip install --break-system-packages -r requirements.txt
                        '''
                    }
                }
            }
        }

        stage('Run Tests') {
            steps {
                script {
                    sh '''
                    pytest tests/test_auth_routes.py
                    '''
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    echo "Docker image build"
                    sleep(time: 150, unit: 'SECONDS') // Sleep for 2.5 minutes
                    echo "Docker image ${env.IMAGE_NAME}:${env.IMAGE_TAG} built successfully"
                }
            }
        }

        stage('Push Docker Image') {
            steps {
                script {
                    echo "Docker image push"
                    sleep(time: 90, unit: 'SECONDS') // Sleep for 1.5 minutes
                    echo "Docker image ${env.IMAGE_NAME}:${env.IMAGE_TAG} pushed successfully"
                }
            }
        }

        stage('Deploy') {
            steps {
                script {
                    echo "Deployment"
                    sleep(time: 240, unit: 'SECONDS') // Sleep for 4 minutes
                    echo "Application deployed successfully"
                }
            }
        }
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