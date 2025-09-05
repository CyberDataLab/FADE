/**
 * @summary Class representing a user in the system.
 * 
 * This model includes authentication and profile details as well as user-related statistics
 * such as login counts, password changes, created designs, and executed scenarios.
 */
export class User {
  /** @summary Unique identifier of the user */
  id: string;

  /** @summary Username used for login */
  username: string;

  /** @summary Hashed or plaintext password (depending on context) */
  password: string;

  /** @summary User's first name */
  first_name: string;

  /** @summary User's last name */
  last_name: string;

  /** @summary Email address of the user */
  email: string;

  /** @summary Number of times the user has logged in */
  numberTimesConnected: number;

  /** @summary Number of times the user has modified their password */
  numberTimesModifiedPassword: number;

  /** @summary Total number of scenario designs the user has created */
  numberDesignsCreated: number;

  /** @summary Total number of scenarios the user has executed */
  numberExecutedScenarios: number;

  /**
   * @summary Creates a new user instance.
   * 
   * @param id Unique user identifier
   * @param username Username of the user
   * @param password User's password
   * @param first_name First name of the user
   * @param last_name Last name of the user
   * @param email Email address of the user
   */
  constructor(
    id: string,
    username: string,
    password: string,
    first_name: string,
    last_name: string,
    email: string
  ) {
    this.id = id;
    this.username = username;
    this.password = password;
    this.first_name = first_name;
    this.last_name = last_name;
    this.email = email;

    // Initialize statistics
    this.numberTimesConnected = 0;
    this.numberTimesModifiedPassword = 0;
    this.numberDesignsCreated = 0;
    this.numberExecutedScenarios = 0;
  }
}
