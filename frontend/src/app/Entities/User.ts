export class User{
    id: String;
    username: String;
    password: String;
    first_name: String;
    last_name: String;
    email: String; 

    // Statistics
    numberTimesConnected: number;
    numberTimesModifiedPassword: number;
    numberDesignsCreated: number;
    numberExecutedScenarios: number;

    constructor(id: String, username: String, password: String, first_name: String, last_name: String, email: String) {
      this.id = id;
      this.username = username;
      this.password = password;
      this.first_name = first_name;
      this.last_name = last_name;
      this.email = email;
      this.numberTimesConnected = 0;
      this.numberTimesModifiedPassword = 0;
      this.numberDesignsCreated = 0;
      this.numberExecutedScenarios = 0;
    }
}