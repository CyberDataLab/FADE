// Angular core and common modules
import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, FormsModule, ReactiveFormsModule } from '@angular/forms';

// Application-specific service and DTO
import { AuthenticationService } from '../../Authentication/authentication.service';
import { Password } from '../../DTOs/Password';

/**
 * @summary Component for managing user profile and password settings.
 * 
 * This component allows the authenticated user to view and edit their personal information
 * (username, name, email), as well as securely change their password.
 */
@Component({
  selector: 'app-user',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    FormsModule
  ],
  templateUrl: './user.component.html',
  styleUrls: ['./user.component.css']
})
export class UserComponent implements OnInit {

  /** @summary Logged-in user information */
  user: any;

  /** @summary Flags for UI state */
  isEditing = false;
  isChangingPassword = false;
  userForm: FormGroup;

  /** @summary Reactive form for user profile editing */
  isPasswordModalOpen = false;

  /** @summary DTO for password change form */
  passwordDTO: Password = {
    current_password: '',
    new_password: '',
    confirm_password: ''
  };

  /** @summary Field validation error flags */
  current_passwordError: boolean;
  passwordError: boolean;
  confirm_passwordError: boolean;
  badPasswordError: boolean;
  badConfirmPasswordError: boolean;
  
  /** @summary Toggles for showing/hiding password fields */
  showCurrentPassword: boolean;
  showNewPassword: boolean;
  showConfirmPassword: boolean;

  /** @summary Password pattern for validation (min 8 chars, uppercase, lowercase, number) */
  passwordPattern = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z\d]{8,}$/;

  /**
   * @summary Injects services and initializes form controls and flags.
   * 
   * @param authService Authentication service to access user info and update password
   * @param fb Angular FormBuilder for reactive form construction
   */
  constructor(
    private authService: AuthenticationService,
    private fb: FormBuilder
  ) {
    this.userForm = this.fb.group({
      username: [''],
      first_name: [''],
      last_name: [''],
      email: ['']
    });

    // Initialize flags
    this.current_passwordError = false;
    this.passwordError = false;
    this.confirm_passwordError = false;
    this.badPasswordError = false;
    this.badConfirmPasswordError = false;
    this.showCurrentPassword = false;
    this.showNewPassword = false;
    this.showConfirmPassword = false;
  }

  /**
   * @summary Loads user info and populates the form on component initialization.
   */
  ngOnInit(): void {
    this.authService.getInfoActualUser().subscribe(data => {
      this.user = data;
      this.userForm.patchValue({
        username: this.user.username,
        first_name: this.user.first_name,
        last_name: this.user.last_name,
        email: this.user.email
      });
    });
  }

  /**
   * @summary Triggers password change on Enter key press.
   * 
   * @param event KeyboardEvent from user input
   */
  keyDownFunction(event: KeyboardEvent): void{
    if (event.key === 'Enter'){
      this.changePassword();
    }
  }

  /**
   * @summary Toggles visibility of password input fields.
   * 
   * @param field Field identifier: 'current' | 'new' | 'confirm'
   */
  toggleVisibility(field: 'current' | 'new' | 'confirm'): void {
    if (field === 'current') this.showCurrentPassword = !this.showCurrentPassword;
    if (field === 'new') this.showNewPassword = !this.showNewPassword;
    if (field === 'confirm') this.showConfirmPassword = !this.showConfirmPassword;
  }

  /**
   * @summary Enables edit mode for the user profile form.
   */
  enableEdit(): void {
    this.isEditing = true;
  }

  /**
   * @summary Cancels profile editing and resets edit flag.
   */
  cancelEdit(): void {
    this.isEditing = false;
  }

  /**
   * @summary Saves changes to the user profile.
   * 
   * Updates backend and reloads the user data on success.
   */
  saveChanges(): void {
    const updatedUser = this.userForm.value;
    this.authService.updateUser(updatedUser).subscribe(() => {
      this.authService.getInfoActualUser().subscribe(data => {
        this.user = data;
        this.isEditing = false;
        alert('User information updated successfully');
      });
    });
  }

  /**
   * @summary Enables password change mode.
   */
  enableChangePassword(): void {
    this.isChangingPassword = true;
  }
  
  /**
   * @summary Cancels the password change form and resets fields.
   */
  cancelChangePassword(): void {
    this.isChangingPassword = false;
    this.passwordDTO = { current_password: '', new_password: '', confirm_password: '' };
  }

  /**
   * @summary Validates and submits the password change form.
   * 
   * Handles field validation, pattern checks, password match,
   * and sends request to the authentication service.
   */
  changePassword(): void {
    // Reset validation flags
    this.current_passwordError = false;
    this.passwordError = false;
    this.confirm_passwordError = false;

    // Validate required fields
    if (this.passwordDTO.current_password === '') {
      this.current_passwordError = true;
    }

    if (this.passwordDTO.new_password === '') {
      this.passwordError = true; 
    } else if (!this.passwordPattern.test(this.passwordDTO.new_password)) {
      this.badPasswordError = true;
    }

    if (this.passwordDTO.confirm_password === '') {
      this.confirm_passwordError = true; 
    } else if (!this.passwordPattern.test(this.passwordDTO.confirm_password)) {
      this.badConfirmPasswordError = true;
    }

    // Proceed if all validations pass
    if (
      this.passwordDTO.current_password !== '' &&
      this.passwordDTO.new_password !== '' &&
      this.passwordDTO.confirm_password !== '' &&
      !this.current_passwordError &&
      !this.badPasswordError &&
      !this.badConfirmPasswordError
    ) {
      if (this.passwordDTO.new_password != this.passwordDTO.confirm_password) {
        alert("Passwords dont match")
      } else {
        const { current_password, new_password, confirm_password } = this.passwordDTO;
        this.authService.changePassword({ current_password, new_password }).subscribe(
          () => {
            this.authService.getInfoActualUser().subscribe(data => {
              this.user = data;
              alert('Password changed successfully');
              this.cancelChangePassword();
            });
          },
          error => {
            alert('Error changing password: ' + error.error.message);
          }
        );
      }
    }
  }
}
