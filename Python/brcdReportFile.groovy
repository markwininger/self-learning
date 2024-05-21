def execute_script_by_region(String region) {
    withCredentials([
        usernamePassword(
            credentialsId: 'brcd_admin',
            usernameVariable: 'brcd_user',
            passwordVariable: 'brcd_pass'
        ),
    ]) {
        sh 'python3 brcdReport.py'
    }
    stash  name: region + '_reports', includes: '*.csv'
}
def artifact_and_clean_workspace() {
    archiveArtifacts allowEmptyArchive: true, artifacts: "*.csv", onlyIfSuccessful: true
    cleanWs()
}
pipeline {
    agent none
    triggers {
        cron('30 07 * * *')
    }
    stages {
        stage('Brocade Report') {
            agent {
                label 'cissajenkins01lxv'
            }
            environment {
                nodes = '172.24.198.136,172.24.198.139,172.21.198.136,172.21.198.139'
                outfile1 = 'switch_report.csv'
                outfile2 = 'error_report.csv'
            }
            steps {
                execute_script_by_region("far")
            }
        }
        stage('Send Email') {
            agent {
                label 'cissajenkins01lxv'
            }
            environment {
                sender = 'storagesvc@mitchell.com'
                recipient = 'mark.wininger@Enlyte.com'
                subject = 'Brocade Switch Report'
                emailTitle = 'Brocade Switch Report'
                tableNames = 'Switch Report,Error Report'
                csvFiles = 'switch_report.csv,error_report.csv'
            }
            steps {
                unstash 'far_reports'

                // concatenate all files into one
                // sh 'cat report-name_??.csv > report-name.csv'

                // send the email
                sh 'python3 doEmail.py'
            }
        }

    }
    post {
        success {

            node('cissajenkins01lxv') {
                artifact_and_clean_workspace()
            }
        }
    }
}
