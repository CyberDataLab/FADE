export class User{
    id: String;
    user: String;
    password: String;
    first_name: String;
    last_name: String;
    email: String; 

    constructor(id: String, user: String, password: String, first_name: String, last_name: String, email: String) {
        this.id = id;
        this.user = user;
        this.password = password;
        this.first_name = first_name;
        this.last_name = last_name;
        this.email = email;
      }
}