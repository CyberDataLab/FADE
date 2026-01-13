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

4. On the host system, set correct permissions:
   ```sh
   sudo chown -R <username>:<username> ~/defender_software/ssh_keys
   chmod 700 ~/defender_software/ssh_keys
   chmod 600 ~/defender_software/ssh_keys/id_ed25519
   chmod 644 ~/defender_software/ssh_keys/id_ed25519.pub
   ```
   Replace <username> with your actual host username.

5. To verify SSH connectivity, enter the backend container and run:
   ```sh
   ssh -i /root/.ssh/id_ed25519 -o StrictHostKeyChecking=no <username>@host.docker.internal true
   ```
   Replace <username> with your actual host username.

   This will generate known_hosts automatically.

6. Now, copy the content of id_ed25519.pub and paste it into:
   ```sh
   ~/.ssh/authorized_keys
   ```
    on the host machine.


7. To start the docker-compose.yml, run the following command in the project root directory:
   ```sh
   ./start.sh --mode <mode>   
   ```
   Replace <mode> with cpu or gpu.

8. Once the containers for the frontend, backend, and database are up and running, run the following command to check the container names:
   ```sh
   docker ps
   ```

9. Initialize the database (create empty tables) and create a superuser if you are starting the application for the first time.

   Enter the backend container:

   ```sh
   docker exec -ti <backend_container_name> sh
   ```

   Apply Django migrations to create all database tables:

   ```sh
   python manage.py migrate
   ```

   Create a Django superuser (only required the first time):

   ```sh
   python manage.py createsuperuser
   ```

10. To access the frontend, go to the following address in your browser:
   ```sh
   http://localhost:4200
   ```

11. Log in using the credentials created in the previous step.

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

## Optional: Email alert configuration

If you want to create alert policies that send notification emails, you must create a `.env` file in the project root directory.

Add the following environment variables:

```text
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your_email_to_send_alerts
EMAIL_HOST_PASSWORD=your_app_password_here
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
```

### Important notes

- The `.env` file **must not be committed** to the repository.
- Use a **Gmail App Password**, not your real Gmail password.
- This configuration is only required if you plan to use **email-based alert policies**.

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

1. For production, add the following line to your sudoers configuration (via sudo visudo -f /etc/sudoers.d/tools), replacing <username> with your actual Linux username:
   ```text
   <username> ALL=(ALL) NOPASSWD: /usr/bin/tshark
   ```
   This allows the system to run tshark for live traffic capture without asking for a password.

2. For policy management, add this line to your sudoers configuration:
   ```text
   <username> ALL=(ALL) NOPASSWD: /usr/sbin/iptables, /usr/sbin/ip, /usr/bin/tee, /usr/bin/bpftrace
   ```
   This allows your user to manage firewall policies without requiring a password each time.

