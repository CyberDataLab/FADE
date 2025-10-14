# Project Setup and Execution

## Steps to get the project up and running:

1. Clone the project repository using the following command:
   ```sh
   git clone elopez@deeplearning.inf.um.es:/home/repositorios/defender_software.git
   ```

2. Once the repository has been cloned, you need to generate an SSH key in order to run the production module. Use the following command:
   ```sh
   ssh-keygen -t ed25519 -C <your_email>
   ```
   Replace <your_email> with your email address.

3. Create a directory in the project root directory called ‘ssh_keys’ and copy into it the two files generated in the previous step: 'id_ed25519' and 'id_ed25519.pub'.

4. To start the docker-compose.yml, run the following command in the project root directory:
   ```sh
   ./start.sh --mode <mode>   
   ```
   Replace <mode> with cpu or gpu.

5. Once the containers for the frontend, backend, and database  are up and running, run the following command to check the container names:
   ```sh
   docker ps
   ```

6. The last modification of the database is stored in the backup.sql file located in the project root directory. To load the data, run the following command from the terminal while in the project root directory:
   ```sh
   docker cp backup.sql <database_container_name>:/backup.sql
   ```
   Replace <database_container_name> with the actual name of the database container returned by the previous docker ps command.

7. Access the database container with the following command:
   ```sh
   docker exec -ti <database_container_name> sh
   ```
   Replace <database_container_name> with the actual name of the database container returned by the previous docker ps command.

8. Run the following command to restore the database:
   ```sh
   mysql -u root -p defender < /backup.sql
   ````

9. To access the frontend, go to the following address in your browser:
   ```sh
   localhost:4200
   ```

10. If you are starting the application for the first time, you need to create a super user. To do this, enter in the backend container:
   ```sh
   docker exec -ti <backend_container_name> sh
   ```
   Replace <backend_container_name> with the actual name of the backend container returned by the previous docker ps command.

11. Once inside the backend container, run the following command to create a Django superuser. You will be prompted to enter a username, email, and password:
    ```sh
   python manage.py createsuperuser
   ```

12. Now you can access in the frontend using the credentials created in the previous step.

## After stopping the project:

1. Run the following command from the database container to dump the latest database state:
   ```sh
   mysqldump -u root -p defender > backup.sql
   ```
2. Replace the backup.sql file in the project root directory with the latest database dump.

## To implement the policies, if you are running the project on a macOS must follow these steps:

1. To enable the rules, run the following command:
   ```sh
   sudo pfctl -e
   ```
   You should see 'pfctl: pf enabled'.

2. Create a file that will contain the desired rules:
   ```sh
   sudo touch /etc/pf-block.rules
   ```

3. In the /etc/pf.conf file, add the following lines at the end:
   ```text
   anchor "blockrules"
   load anchor "blockrules" from "/etc/pf-block.rules"
   ```
   
4. If you want to delete a rule, edit the '/etc/pf-block.rules' file to remove it, and then run the following command to reload the rules:
   ```sh
   sudo pfctl -a blockrules -f /etc/pf-block.rules
   ```
   This allows the system to run tshark for live traffic capture without asking for a password.

## Additional configuration 

### On macOS

1. For production, add the following line to your sudoers configuration (via sudo visudo), replacing <username> with your actual macOS username:
   ```text
   <username> ALL=(ALL) NOPASSWD: /opt/homebrew/bin/tshark
   ```
   This allows the system to run tshark for live traffic capture without asking for a password.

2. For policy management, add this line to your sudoers configuration:
   ```text
   <username> ALL=(ALL) NOPASSWD: /sbin/pfctl, /sbin/dnctl, /sbin/ifconfig, /usr/bin/tee
   ```
   This enables your user to manage pfctl policies without requiring a password each time.

### On Linux

1. For production, add the following line to your sudoers configuration (via sudo visudo), replacing <username> with your actual Linux username:
   ```text
   <username> ALL=(ALL) NOPASSWD: /usr/bin/tshark
   ```
   This allows the system to run tshark for live traffic capture without asking for a password.

2. For policy management, add this line to your sudoers configuration:
   ```text
   <username> ALL=(ALL) NOPASSWD: /usr/sbin/iptables, /usr/sbin/ip, /usr/bin/tee
   ```
   This allows your user to manage firewall policies without requiring a password each time.

