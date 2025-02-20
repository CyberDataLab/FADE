import { Component, OnInit } from '@angular/core'
import { Router} from '@angular/router';
import { first } from 'rxjs/operators';
import { CommonModule } from '@angular/common'; // Importa CommonModule
import { FormsModule } from '@angular/forms'; // Si usas formularios en el template
import { RouterModule } from '@angular/router';
import { UserLogin } from '../../DTOs/UserLogin';
import { AuthenticationService } from '../authentication.service';

@Component({
    selector: 'app-login',
    imports: [CommonModule,
        FormsModule,
        RouterModule
    ],
    templateUrl: './login.component.html',
    styleUrl: './login.component.css'
})
export class LoginComponent implements OnInit {

  userLoginDTO: UserLogin = {
    username: '',
    password: ''
  };

  usernameError: boolean;
  passwordError: boolean;
  showPassword: boolean;

  constructor(private authenticationService: AuthenticationService, private router: Router) { 
    this.usernameError = false;
    this.passwordError = false;
    this.showPassword = false;
  }

  ngOnInit(): void {
    if(this.authenticationService.actualUserValue != null){
      this.router.navigate(["/dashboard"]);
    }
  }

  togglePasswordVisibility() {
    this.showPassword = !this.showPassword;
  }

  keyDownFunction(event: KeyboardEvent): void{
    if (event.key === 'Enter'){
      this.login();
    }
  }

  login() {
    this.usernameError = false;
    this.passwordError = false;

    if (this.userLoginDTO.username === '') {
      this.usernameError = true;
    }

    if (this.userLoginDTO.password === '') {
      this.passwordError = true;
    }

    if (this.userLoginDTO.username !== '' && this.userLoginDTO.password !== '') {
      this.usernameError = false;
      this.passwordError = false;
      const loginObs = this.authenticationService.login(this.userLoginDTO);

      if (loginObs) {
        loginObs.pipe(first())
          .subscribe(
            data => {
              this.router.navigate(["/dashboard"]);
            },
            error => {
              alert('Wrong user or password.');
              
            }
          );
      } else {
        alert('You are already logged in.');
        this.router.navigate(["/dashboard"]);
      }
    } 
  }
}
