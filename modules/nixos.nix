{ config, lib, ... }:

let
  cfg = config.programs.epic-games-launcher;
in
{
  imports = [ ./options.nix ];

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [ cfg.package ];
  };
}
