export class User{
    id: String;
    user: String;
    password: String;
    name: String;
    lastName: String;
    email: String; 

    constructor(id: String, user: String, password: String, name: String, lastName: String, email: String) {
        this.id = id;
        this.user = user;
        this.password = password;
        this.name = name;
        this.lastName = lastName;
        this.email = email;
      }
}