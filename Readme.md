# Project Setup and Execution

## Steps to get the project up and running:

1. Clone the project repository using the following command:
   ```sh
   git clone elopez@deeplearning.inf.um.es:/home/repositorios/defender_software.git
   ```

2. To start the docker-compose.yml, run the following command in the project root directory:
   ```sh
   docker-compose up --build
   ```

3. Once the containers for the frontend, backend, and database (DB) are up and running, execute the following command to check the container names:
   ```sh
   docker ps
   ```

4. The last modification of the DB is stored in the backup.sql file located in the project root directory. To load the data, execute the following command from the terminal while in the project root directory:
   ```sh
   docker cp backup.sql <db_container_name>:/backup.sql
   ```
   Replace <db_container_name> with the actual name of the database container returned by the previous docker ps command.

5. Access the DB container with the following command:
   ```sh
   docker exec -ti <db_container_name> sh
   ```
   Replace <db_container_name> with the actual name of the database container returned by the previous docker ps command.

6. Run the following command to restore the DB:
   ```sh
   mysql -u root -p defender < /backup.sql
   ````

7. To access the frontend, go to the following address in your browser:
   ```sh
   localhost:4200
   ```

8. If you are starting the application for the first time, you need to create a super user. To do this, enter in the backend container:
   ```sh
   docker exec -ti <backend_container_name> sh
   ```
   Replace <backend_container_name> with the actual name of the backend container returned by the previous docker ps command.

9. Once inside the backend container, run the following command to create a Django superuser. You will be prompted to enter a username, email, and password:
    ```sh
   python manage.py createsuperuser
   ```

10. Now you can access in the frontend using the credentials created in the previous step.

## After the project has finished running:

1. Execute the following command from the DB container to dump the latest database state:
   ```sh
   mysqldump -u root -p defender > backup.sql
   ```
2. Modify the backup.sql file in the project root directory to save the latest database update.
